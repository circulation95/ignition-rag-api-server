from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition

from app.graph.nodes import (
    aggregate_results,
    alarm_agent,
    alarm_tools_node,
    # Legacy approval nodes (backward compatibility)
    chat_tools_node_with_approval,
    check_pending_actions,
    request_approval,
    # Modern interrupt-based HITL (LangGraph 1.x)
    execute_tool_with_approval,
    process_human_approval,
    # Other nodes
    generate_chat,
    generate_rag,
    historian_agent,
    historian_tools_node,
    intent_router,
    knowledge_agent,
    operations_agent,
    retrieve_rag,
    sql_react_agent,
    supervisor_router,
    validate_agent_response,
)
from app.graph.state import GraphState


def _route_decision(state: GraphState):
    return state["intent_category"]


def _check_query_complexity(state: GraphState):
    """
    Determine if query requires supervisor orchestration or can use fast path.

    Complex queries involve:
    - Analysis, comparison, investigation keywords
    - Multi-domain reasoning (e.g., "analyze current alarm" needs alarm + operations + historian)

    Simple queries:
    - Single domain (read tag, get history, search doc)
    """
    query = state.get("payload", "")
    intent = state.get("intent_category", "chat")

    # Keywords that indicate complex multi-domain queries
    complex_keywords = [
        "분석",
        "비교",
        "원인",
        "조사",
        "알람 분석",
        "현재 알람",
        "트러블슈팅",
        "진단",
        "검증",
    ]

    if any(keyword in query for keyword in complex_keywords):
        print(f"[Router] Complex query detected: '{query}' → supervisor")
        return "supervisor"

    # Simple queries use fast paths
    print(f"[Router] Simple query detected → {intent} fast path")
    return intent


def _check_aggregation_ready(state: GraphState):
    """Check if aggregation is complete and ready to end."""
    is_ready = state.get("aggregation_ready", False)
    if is_ready:
        print("[Router] Aggregation complete, ending workflow")
        return END
    else:
        print("[Router] Aggregation not ready, continuing to wait")
        # This shouldn't happen with proper barrier, but handle gracefully
        return END


def _route_to_agents_sequential(state: GraphState):
    """
    Route supervisor to required agents sequentially.

    NOTE: Temporary sequential execution due to langgraph<1.1.0 compatibility.
    When langchain supports langgraph>=1.2.0, upgrade to Send API for parallel execution.
    """
    required = state.get("required_agents", [])
    completed_count = state.get("agents_completed", 0)

    if not required or completed_count >= len(required):
        # All agents processed, go to aggregation
        print(
            f"[Router] All {completed_count} agents completed, proceeding to aggregation"
        )
        return "aggregate_results"

    # Map agent names to node names
    agent_node_map = {
        "operations": "operations_agent",
        "historian": "historian_agent",
        "alarm": "alarm_agent",
        "knowledge": "knowledge_agent",
    }

    # Route to next required agent based on completion count
    next_agent = required[completed_count]
    node_name = agent_node_map.get(next_agent, "aggregate_results")
    print(
        f"[Router] Dispatching to {next_agent} ({completed_count + 1}/{len(required)}, sequential)"
    )

    return node_name


def next_agent_router(state: GraphState):
    """Passthrough node for routing to next agent without re-running supervisor."""
    # This node doesn't modify state, just serves as a routing point
    return state


def build_graph(checkpointer=None, use_modern_hitl: bool = True):
    """
    Build the LangGraph workflow with optional modern HITL support.

    Args:
        checkpointer: Checkpointer instance (AsyncSqliteSaver or MemorySaver)
                     If None, graph will not persist state
        use_modern_hitl: If True, use LangGraph 1.x interrupt-based HITL (recommended)
                        If False, use legacy approval workflow (backward compatibility)

    Returns:
        Compiled StateGraph with checkpointer
    """
    workflow = StateGraph(GraphState)

    # ============================================================================
    # Add Nodes
    # ============================================================================

    # Legacy nodes (backward compatibility)
    workflow.add_node("intent_router", intent_router)
    workflow.add_node("retrieve_rag", retrieve_rag)
    workflow.add_node("generate_rag", generate_rag)
    workflow.add_node("generate_chat", generate_chat)
    workflow.add_node("sql_react_agent", sql_react_agent)

    # Phase 1: Safety layer nodes
    if use_modern_hitl:
        # Modern interrupt-based HITL (LangGraph 1.x)
        workflow.add_node("chat_tools_node", execute_tool_with_approval)
        workflow.add_node("process_approval", process_human_approval)
    else:
        # Legacy approval workflow (backward compatibility)
        workflow.add_node("chat_tools_node", chat_tools_node_with_approval)
        workflow.add_node("request_approval", request_approval)

    # Phase 2: Supervisor + specialized agents
    workflow.add_node("supervisor_router", supervisor_router)
    workflow.add_node("next_agent_router", next_agent_router)  # Passthrough for routing
    workflow.add_node("operations_agent", operations_agent)
    workflow.add_node("historian_agent", historian_agent)
    workflow.add_node("historian_tools_node", historian_tools_node)
    workflow.add_node("alarm_agent", alarm_agent)
    workflow.add_node("alarm_tools_node", alarm_tools_node)
    workflow.add_node("knowledge_agent", knowledge_agent)
    workflow.add_node("aggregate_results", aggregate_results)

    # ============================================================================
    # Entry Point
    # ============================================================================

    workflow.add_edge(START, "intent_router")

    # ============================================================================
    # Intent Router → Fast Path or Supervisor
    # ============================================================================

    workflow.add_conditional_edges(
        "intent_router",
        _check_query_complexity,
        {
            "supervisor": "supervisor_router",  # Complex multi-domain queries
            "sql_search": "sql_react_agent",  # Fast path: historical data
            "rag_search": "retrieve_rag",  # Fast path: documentation
            "chat": "generate_chat",  # Fast path: real-time operations
        },
    )

    # ============================================================================
    # Supervisor → Specialized Agents (SEQUENTIAL EXECUTION)
    # ============================================================================
    # NOTE: Using sequential execution due to langgraph<1.1.0 compatibility
    # When langchain supports langgraph>=1.2.0, upgrade to Send API for parallel execution

    # Supervisor routes to next_agent_router, which then routes to actual agents
    workflow.add_edge("supervisor_router", "next_agent_router")

    # next_agent_router decides which agent to run next or if we're done
    workflow.add_conditional_edges(
        "next_agent_router",
        _route_to_agents_sequential,
        {
            "operations_agent": "operations_agent",
            "historian_agent": "historian_agent",
            "alarm_agent": "alarm_agent",
            "knowledge_agent": "knowledge_agent",
            "aggregate_results": "aggregate_results",
        },
    )

    # ============================================================================
    # Agent Execution → Next Agent Router (SEQUENTIAL - Phase 3)
    # ============================================================================
    # After each agent completes, route back to next_agent_router (not supervisor!)
    # This prevents re-running supervisor analysis

    # Operations agent: simple execution (no ReAct loop needed for real-time reads)
    workflow.add_edge("operations_agent", "next_agent_router")

    # Historian agent: ReAct loop with tools
    workflow.add_conditional_edges(
        "historian_agent",
        tools_condition,
        {
            "tools": "historian_tools_node",
            END: "next_agent_router",
        },
    )
    workflow.add_edge(
        "historian_tools_node", "historian_agent"
    )  # Loop back for more reasoning

    # Alarm agent: ReAct loop with tools
    workflow.add_conditional_edges(
        "alarm_agent",
        tools_condition,
        {
            "tools": "alarm_tools_node",
            END: "next_agent_router",
        },
    )
    workflow.add_edge("alarm_tools_node", "alarm_agent")  # Loop back for more reasoning

    # Knowledge agent: simple RAG retrieval (no tool execution)
    workflow.add_edge("knowledge_agent", "next_agent_router")

    # Aggregation conditional end (waits for all agents via barrier)
    workflow.add_conditional_edges(
        "aggregate_results",
        _check_aggregation_ready,
        {
            END: END,
        },
    )

    # ============================================================================
    # Legacy Fast Paths (Backward Compatibility)
    # ============================================================================

    # RAG path
    workflow.add_edge("retrieve_rag", "generate_rag")
    workflow.add_edge("generate_rag", END)

    # SQL path
    workflow.add_edge("sql_react_agent", END)

    # Chat path with approval workflow
    workflow.add_conditional_edges(
        "generate_chat",
        tools_condition,
        {"tools": "chat_tools_node", END: END},
    )

    if use_modern_hitl:
        # Modern HITL: interrupt() automatically pauses the graph
        # When resumed with Command, execution continues naturally
        workflow.add_conditional_edges(
            "chat_tools_node",
            tools_condition,
            {
                "tools": "generate_chat",  # Continue tool loop
                END: END,
            },
        )
    else:
        # Legacy HITL: manual approval routing
        workflow.add_conditional_edges(
            "chat_tools_node",
            check_pending_actions,
            {
                "approval": "request_approval",
                "continue": "generate_chat",
                "end": END,
            },
        )
        workflow.add_edge("request_approval", END)

    return workflow.compile(checkpointer=checkpointer)
