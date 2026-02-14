from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, Send
from langgraph.prebuilt import tools_condition

from app.graph.nodes import (
    aggregate_results,
    alarm_agent,
    chat_tools_node_with_approval,
    check_pending_actions,
    generate_chat,
    generate_rag,
    historian_agent,
    intent_router,
    knowledge_agent,
    operations_agent,
    request_approval,
    retrieve_rag,
    sql_react_agent,
    supervisor_router,
    validate_agent_response,  # Phase 3: Validation node
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


def _route_to_agents_parallel(state: GraphState):
    """
    Route supervisor to all required agents in parallel using Send API.

    Phase 3 Enhancement: Parallel execution for improved performance.
    All required agents execute simultaneously and results are aggregated.
    """
    required = state.get("required_agents", [])

    if not required:
        # No agents required, go directly to aggregation
        print("[Router] No agents required, skipping to aggregation")
        return []

    # Map agent names to node names
    agent_node_map = {
        "operations": "operations_agent",
        "historian": "historian_agent",
        "alarm": "alarm_agent",
        "knowledge": "knowledge_agent",
    }

    # Create Send objects for parallel execution
    sends = []
    for agent_name in required:
        node_name = agent_node_map.get(agent_name)
        if node_name:
            print(f"[Router] Dispatching to {agent_name} (parallel)")
            sends.append(Send(node_name, state))
        else:
            print(f"[Router] Warning: Unknown agent '{agent_name}', skipping")

    return sends if sends else []


def build_graph():
    memory = MemorySaver()
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
    workflow.add_node("chat_tools_node", chat_tools_node_with_approval)
    workflow.add_node("request_approval", request_approval)

    # Phase 2: Supervisor + specialized agents
    workflow.add_node("supervisor_router", supervisor_router)
    workflow.add_node("operations_agent", operations_agent)
    workflow.add_node("historian_agent", historian_agent)
    workflow.add_node("alarm_agent", alarm_agent)
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
    # Supervisor → Specialized Agents (PARALLEL EXECUTION - Phase 3)
    # ============================================================================
    # Using Send API to dispatch to multiple agents in parallel
    # After all agents complete, results are automatically aggregated

    workflow.add_conditional_edges(
        "supervisor_router",
        _route_to_agents_parallel,
        # No path mapping needed - Send API handles routing
    )

    # ============================================================================
    # Agent Execution → Aggregation (PARALLEL COLLECTION - Phase 3)
    # ============================================================================
    # All agents flow to aggregation after completing
    # Aggregation uses barrier synchronization to wait for all agents

    workflow.add_edge("operations_agent", "aggregate_results")
    workflow.add_edge("historian_agent", "aggregate_results")
    workflow.add_edge("alarm_agent", "aggregate_results")
    workflow.add_edge("knowledge_agent", "aggregate_results")

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

    return workflow.compile(checkpointer=memory)
