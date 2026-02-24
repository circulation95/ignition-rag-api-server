from langgraph.types import interrupt
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from app.core.llm_factory import get_llm
from app.graph.state import (
    GraphState,
    HumanFeedback,
    IntentRouterOutput,
    SupervisorRouterOutput,
)
from app.graph.prompts import (
    SUPERVISOR_PROMPT,
    OPERATIONS_AGENT_PROMPT,
    HISTORIAN_AGENT_PROMPT,
    ALARM_AGENT_PROMPT,
    KNOWLEDGE_AGENT_PROMPT,
    AGGREGATION_PROMPT,
)
from app.services.vectorstore import get_retriever
from app.tools import chat_tools_list
from app.tools.tag_history_tools import tag_history_tools_list
from app.tools.alarm_tools import alarm_tools_list


def intent_router(state: GraphState):
    print("[Router] Intent classification...")
    question = state["messages"][-1].content

    llm = get_llm(temperature=0)
    # json_mode: OpenAI 전용 structured-outputs 대신 범용 JSON 모드 사용
    # (Qwen, Claude 등 대부분의 모델이 지원)
    llm_with_structure = llm.with_structured_output(IntentRouterOutput, method="json_mode")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a smart router. Classify the user question into one of three categories:

1. 'sql_search': Questions about historical/past data, trends, logs, averages, statistics, database queries, OR ALARM HISTORY/EVENTS.
   - Data Keywords: 평균, 최대, 최소, 합계, 트렌드, 로그, 기록, 히스토리, 과거, 어제, 지난주, 특정 날짜
   - Alarm Keywords: 알람, 경보, 발생, 언제, 최근, alarm, event, 이벤트, 알람 이력, 알람 기록, 가장 최근
   - Examples:
     - "2026년 1월 18일 FAN1 평균 RPM은?" → sql_search
     - "어제 Tank1 최고 온도는?" → sql_search
     - "가장 최근에 발생한 알람" → sql_search (알람 발생 이력 조회)
     - "FAN1 알람이 최근에 언제 발생했어?" → sql_search
     - "지난주 Smoke 알람 몇 번 발생했어?" → sql_search
     - "알람 통계 보여줘" → sql_search
     - "최근 알람 목록" → sql_search

2. 'rag_search': Questions asking for definitions, manuals, troubleshooting guides, specifications, or general knowledge.
   - Keywords: 무엇, 정의, 매뉴얼, 가이드, 스펙, 사양, 에러코드, 알람코드 의미, 설명, 어떻게
   - Examples:
     - "PID 제어란 무엇인가요?" → rag_search
     - "알람 코드 E001 의미는?" → rag_search (알람 코드의 '의미'를 묻는 것)
     - "FAN 트러블슈팅 방법" → rag_search

3. 'chat': Requests for CURRENT/real-time values, control commands, greetings, or general chat.
   - Keywords: 현재, 지금, 실시간, 켜줘, 꺼줘, 설정해줘, 안녕
   - Examples:
     - "현재 Tank1 온도 알려줘" → chat
     - "FAN1 켜줘" → chat
     - "지금 온도는?" → chat

CRITICAL RULES:
- ANY question about alarm occurrence, history, or past events → 'sql_search'
- If asking "가장 최근", "최근에", "언제 발생" with alarm → 'sql_search'
- If a specific date/time is mentioned → ALWAYS 'sql_search'
- ONLY if asking about alarm code MEANING/DEFINITION → 'rag_search'

Respond ONLY in valid JSON format: {{"destination": "<category>"}}
""",
            ),
            ("human", "{question}"),
        ]
    )

    chain = prompt | llm_with_structure

    try:
        result: IntentRouterOutput = chain.invoke({"question": question})
        destination = result.destination
    except Exception as e:
        print(f"[Router] Error: {e}, defaulting to chat")
        destination = "chat"

    print(f"[Router] Decision: {destination}")

    return {
        "intent_category": destination,
        "payload": question,
    }


def retrieve_rag(state: GraphState):
    retriever = get_retriever()
    if not retriever:
        return {"documents": []}
    return {"documents": retriever.invoke(state["payload"])}


def generate_rag(state: GraphState):
    context = "\n".join([d.page_content for d in state.get("documents", [])])
    content = f"[RAG 결과]\n참고문서:\n{context[:200]}..."
    return {"messages": [AIMessage(content=content)]}


def generate_chat(state: GraphState):
    llm = get_llm(temperature=0.1)
    llm_with_tools = llm.bind_tools(chat_tools_list)

    system_msg = SystemMessage(
        content="You are an Ignition SCADA Operator. Answer in Korean."
    )
    # Only use the latest user message
    response = llm_with_tools.invoke([system_msg, state["messages"][-1]])
    return {"messages": [response]}


SQL_AGENT_PROMPT = """You are an expert on Ignition SCADA Databases (MariaDB).
You can query both Tag History data and Alarm History data.

## Tag History Tools (태그 히스토리)

1. `parse_date_to_partition(date_string)`: 자연어 날짜를 파티션 정보로 변환
   - 입력: "2025년 9월 1일", "어제", "오늘" 등
   - 출력: year, month, day, expected_table 정보

2. `get_tag_id(tag_name)`: 태그명으로 ID 조회
   - 입력: "FAN1", "Tank1" 등 (부분 일치)
   - 출력: id와 tagpath

3. `get_tag_history(tag_id, year, month, ...)`: 히스토리 데이터 직접 조회
   - tag_id, year, month: 필수
   - start_day, end_day: 일자 범위 (선택)
   - aggregation: "raw", "avg", "max", "min", "sum", "count"

4. `find_partition_table(year, month)`: 파티션 테이블 존재 여부 확인

## Alarm History Tools (알람 히스토리)

5. `get_latest_alarm_for_tag(tag_path)`: 특정 태그의 최근 알람 조회
   - "FAN1 알람 언제 발생?" → get_latest_alarm_for_tag(tag_path="FAN1")

6. `search_alarm_events(tag_path, hours_ago, event_type, limit)`: 알람 이벤트 검색
   - tag_path: 태그 경로 (선택)
   - hours_ago: 최근 N시간 (기본 24)
   - event_type: "active", "clear", "ack" (선택)

7. `get_alarm_statistics(tag_path, days)`: 알람 통계 조회
   - 발생 횟수, 태그별 분포

8. `get_alarm_count_by_period(tag_path, start_date, end_date)`: 기간별 알람 횟수
   - start_date, end_date: "YYYY-MM-DD" 형식

## Workflow Examples

### 태그 히스토리 조회
Q: "2025년 9월 1일 FAN1 평균 RPM은?"
1. parse_date_to_partition("2025년 9월 1일") → year=2025, month=9, day=1
2. get_tag_id("FAN1") → id=5
3. get_tag_history(5, 2025, 9, 1, 1, "avg") → avg_value=1234.5

### 알람 조회
Q: "FAN1 알람이 최근에 언제 발생했어?"
1. get_latest_alarm_for_tag(tag_path="FAN1") → eventtime, source 정보

Q: "지난주 Smoke 알람 통계 알려줘"
1. get_alarm_statistics(tag_path="Smoke", days=7) → 발생 횟수, 분포

Answer in Korean. 숫자와 시간 정보를 명확하게 전달하세요."""


def sql_react_agent(state: GraphState):
    """
    Handle historical data and alarm queries via SQL database.

    Uses ReAct pattern with tag history and alarm tools.
    """
    print("[SQL ReAct Agent] Processing database query...")

    llm = get_llm(temperature=0)
    # 태그 히스토리 도구 + 알람 도구 결합
    combined_tools = tag_history_tools_list + alarm_tools_list

    # Create ReAct agent with specialized SQL prompt
    sql_agent = create_agent(
        model=llm,
        tools=combined_tools,
        system_prompt=SQL_AGENT_PROMPT,
    )

    # Execute agent
    result = sql_agent.invoke(state)

    # Return the result (agent handles state updates internally)
    return result


# ============================================================================
# APPROVAL WORKFLOW NODES (Phase 1: Safety Layer)
# ============================================================================


def chat_tools_node_with_approval(state: GraphState):
    """
    Execute chat tools and extract pending actions for approval workflow.

    This node replaces the standard ToolNode for the chat path to:
    1. Execute tool calls from the LLM
    2. Extract PendingAction objects from write_ignition_tag results
    3. Store them in GraphState and approval_storage
    """
    from langchain_core.messages import ToolMessage
    from app.services.approval_storage import store_pending_action

    # Get the last AI message with tool calls
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        # No tool calls, return unchanged
        return {}

    tool_messages = []
    pending_actions = state.get("pending_actions") or []

    # Execute each tool call
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        print(f"[ToolNode] Executing {tool_name} with args: {tool_args}")

        # Find and execute the tool
        tool_func = None
        for tool in chat_tools_list:
            if tool.name == tool_name:
                tool_func = tool
                break

        if not tool_func:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Tool {tool_name} not found",
                    tool_call_id=tool_id,
                )
            )
            continue

        try:
            # Execute tool
            import asyncio

            if asyncio.iscoroutinefunction(tool_func.func):
                result = asyncio.run(tool_func.func(**tool_args))
            else:
                result = tool_func.func(**tool_args)

            # Check if this is a write operation requiring approval
            if isinstance(result, dict) and "_pending_action" in result:
                # Extract and store pending action
                pending_action = result["_pending_action"]
                pending_actions.append(pending_action)
                store_pending_action(pending_action)

                # Return the approval message
                tool_content = result.get("message", str(result))
            else:
                tool_content = str(result)

            tool_messages.append(
                ToolMessage(
                    content=tool_content,
                    tool_call_id=tool_id,
                )
            )

        except Exception as e:
            print(f"[ToolNode] Error executing {tool_name}: {e}")
            tool_messages.append(
                ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                )
            )

    return {
        "messages": tool_messages,
        "pending_actions": pending_actions if pending_actions else None,
    }


def check_pending_actions(state: GraphState):
    """
    Conditional router: check if there are pending actions requiring approval.

    Returns:
        "approval" if pending actions exist, otherwise continues to END or generate_chat
    """
    pending = state.get("pending_actions")

    if pending and any(action.status == "pending" for action in pending):
        print("[Router] Pending actions detected, routing to approval node")
        return "approval"

    # Check if there are tool calls that need processing
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Continue the tool execution loop
        return "continue"

    # No pending actions and no tool calls, end conversation
    return "end"


def request_approval(state: GraphState):
    """
    Format approval request message when write operations are pending.

    This node is invoked when pending actions are detected.
    It adds a formatted message to the conversation explaining the approval process.
    """
    pending = state.get("pending_actions")

    if not pending:
        return {}

    # Get the most recent pending action
    latest_pending = pending[-1]

    # Create approval request message
    approval_msg = AIMessage(
        content=f"⚠️ **쓰기 작업 승인 필요**\n\n"
        f"**태그:** {latest_pending.tag_path}\n"
        f"**값:** {latest_pending.value}\n"
        f"**위험도:** {latest_pending.risk_level}\n"
        f"**액션 ID:** {latest_pending.id}\n\n"
        f"이 작업을 실행하려면 `/api/v1/approve` 엔드포인트를 사용하여 승인해주세요.\n\n"
        f"**승인 방법:**\n"
        f"```json\n"
        f"POST /api/v1/approve\n"
        f'{{\n  "action_id": "{latest_pending.id}",\n  "approved": true,\n  "operator": "your_name"\n}}\n'
        f"```\n\n"
        f"보류 중인 작업 목록은 `GET /api/v1/pending`로 확인할 수 있습니다."
    )

    return {"messages": [approval_msg]}


# ============================================================================
# PHASE 2: SUPERVISOR-BASED MULTI-AGENT ARCHITECTURE
# ============================================================================


def supervisor_router(state: GraphState):
    """
    Analyze query complexity and determine which specialized agents are needed.

    Returns:
        GraphState with required_agents list populated
    """
    print("[Supervisor] Analyzing query complexity...")

    # Extract only the latest user question (not entire history)
    latest_question = state["messages"][-1].content

    llm = get_llm(temperature=0)
    # json_mode: OpenAI 전용 structured-outputs 대신 범용 JSON 모드 사용
    llm_with_structure = llm.with_structured_output(SupervisorRouterOutput, method="json_mode")

    supervisor_chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system", SUPERVISOR_PROMPT),
                ("human", "{question}"),
            ]
        )
        | llm_with_structure
    )

    try:
        result: SupervisorRouterOutput = supervisor_chain.invoke({"question": latest_question})
        required_agents = result.required_agents
        reasoning = result.reasoning

        print(f"[Supervisor] Required agents: {required_agents}")
        print(f"[Supervisor] Reasoning: {reasoning}")

        return {
            "required_agents": required_agents,
            "agents_completed": 0,  # Initialize parallel execution counter
        }
    except Exception as e:
        print(f"[Supervisor] Error: {e}, defaulting to operations agent")
        return {
            "required_agents": ["operations"],
            "agents_completed": 0,
        }


def operations_agent(state: GraphState):
    """
    Handle real-time operations with safety focus.

    Uses OPC tools with approval workflow for write operations.
    """
    print("[Operations Agent] Processing real-time operations...")

    # Extract only the latest user question
    latest_question = state["messages"][-1].content

    llm = get_llm(temperature=0)
    llm_with_tools = llm.bind_tools(chat_tools_list)

    agent_chain = ChatPromptTemplate.from_messages(
        [
            ("system", OPERATIONS_AGENT_PROMPT),
            ("human", "{question}"),
        ]
    ) | llm_with_tools

    response = agent_chain.invoke({"question": latest_question})

    # Mark message with agent name for aggregation
    response.name = "Operations Agent"

    # Increment parallel execution counter
    completed = state.get("agents_completed", 0) + 1

    return {
        "messages": [response],
        "agents_completed": completed,
    }


def historian_agent(state: GraphState):
    """
    Handle complex multi-domain historical analysis.

    Uses tag history tools for multi-step reasoning.
    """
    print("[Historian Agent] Analyzing historical data...")

    # Extract only the latest user question
    latest_question = state["messages"][-1].content

    llm = get_llm(temperature=0)
    llm_with_tools = llm.bind_tools(tag_history_tools_list)

    agent_chain = ChatPromptTemplate.from_messages(
        [
            ("system", HISTORIAN_AGENT_PROMPT),
            ("human", "{question}"),
        ]
    ) | llm_with_tools

    response = agent_chain.invoke({"question": latest_question})

    # Mark message with agent name for aggregation
    response.name = "Historian Agent"

    # Only increment counter if this is the final answer (no tool calls)
    result = {"messages": [response]}

    if not hasattr(response, "tool_calls") or not response.tool_calls:
        # Final answer without tool calls - mark as complete
        result["agents_completed"] = state.get("agents_completed", 0) + 1
        print("[Historian Agent] Completed (no tool calls)")
    else:
        print(f"[Historian Agent] Tool calls requested: {len(response.tool_calls)}")

    return result


def alarm_agent(state: GraphState):
    """
    Handle alarm event correlation and analysis.

    Uses alarm tools to identify patterns and root causes.
    """
    print("[Alarm Agent] Analyzing alarm events...")

    # Extract only the latest user question
    latest_question = state["messages"][-1].content

    llm = get_llm(temperature=0)
    llm_with_tools = llm.bind_tools(alarm_tools_list)

    agent_chain = ChatPromptTemplate.from_messages(
        [
            ("system", ALARM_AGENT_PROMPT),
            ("human", "{question}"),
        ]
    ) | llm_with_tools

    response = agent_chain.invoke({"question": latest_question})

    # Mark message with agent name for aggregation
    response.name = "Alarm Agent"

    # Only increment counter if this is the final answer (no tool calls)
    result = {"messages": [response]}

    if not hasattr(response, "tool_calls") or not response.tool_calls:
        # Final answer without tool calls - mark as complete
        result["agents_completed"] = state.get("agents_completed", 0) + 1
        print("[Alarm Agent] Completed (no tool calls)")
    else:
        print(f"[Alarm Agent] Tool calls requested: {len(response.tool_calls)}")

    return result


def alarm_tools_node(state: GraphState):
    """Execute alarm tools and return results."""
    from langchain_core.messages import ToolMessage

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        print(f"[Alarm Tools] Executing {tool_name} with args: {tool_args}")

        # Find and execute the tool
        tool_func = None
        for tool in alarm_tools_list:
            if tool.name == tool_name:
                tool_func = tool
                break

        if not tool_func:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Tool {tool_name} not found",
                    tool_call_id=tool_id,
                )
            )
            continue

        try:
            import asyncio
            if asyncio.iscoroutinefunction(tool_func.func):
                result = asyncio.run(tool_func.func(**tool_args))
            else:
                result = tool_func.func(**tool_args)

            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_id)
            )
        except Exception as e:
            print(f"[Alarm Tools] Error: {e}")
            tool_messages.append(
                ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                )
            )

    return {"messages": tool_messages}


def historian_tools_node(state: GraphState):
    """Execute historian tools and return results."""
    from langchain_core.messages import ToolMessage

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        print(f"[Historian Tools] Executing {tool_name} with args: {tool_args}")

        # Find and execute the tool
        tool_func = None
        for tool in tag_history_tools_list:
            if tool.name == tool_name:
                tool_func = tool
                break

        if not tool_func:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Tool {tool_name} not found",
                    tool_call_id=tool_id,
                )
            )
            continue

        try:
            import asyncio
            if asyncio.iscoroutinefunction(tool_func.func):
                result = asyncio.run(tool_func.func(**tool_args))
            else:
                result = tool_func.func(**tool_args)

            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_id)
            )
        except Exception as e:
            print(f"[Historian Tools] Error: {e}")
            tool_messages.append(
                ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                )
            )

    return {"messages": tool_messages}


def knowledge_agent(state: GraphState):
    """
    Handle documentation and troubleshooting search.

    Uses RAG retrieval for contextual information.
    """
    print("[Knowledge Agent] Searching documentation...")

    # Retrieve documents
    retriever = get_retriever()
    if not retriever:
        # Even if retriever is unavailable, increment counter to prevent infinite loop
        completed = state.get("agents_completed", 0) + 1
        no_docs_msg = AIMessage(
            content="지식베이스가 현재 사용 불가능합니다. 문서 검색을 건너뜁니다.",
            name="Knowledge Agent"
        )
        return {
            "messages": [no_docs_msg],
            "agents_completed": completed,
        }

    query = state["payload"]
    docs = retriever.invoke(query)

    # Generate response with context
    llm = get_llm(temperature=0)

    rag_chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system", KNOWLEDGE_AGENT_PROMPT),
                (
                    "human",
                    "컨텍스트:\n{context}\n\n질문: {question}",
                ),
            ]
        )
        | llm
    )

    context = "\n\n".join([doc.page_content for doc in docs[:3]])
    response = rag_chain.invoke({"context": context, "question": query})

    # Mark message with agent name
    if isinstance(response, AIMessage):
        response.name = "Knowledge Agent"

    # Increment parallel execution counter
    completed = state.get("agents_completed", 0) + 1

    return {
        "messages": [response],
        "documents": docs,
        "agents_completed": completed,
    }


def aggregate_results(state: GraphState):
    """
    Synthesize results from multiple specialized agents.

    Phase 3 Enhancement: Parallel execution with barrier synchronization.
    Uses agents_completed counter to determine when all agents are done.
    """
    required_count = len(state.get("required_agents", []))
    completed_count = state.get("agents_completed", 0)

    print(f"[Aggregator] Agent completion: {completed_count}/{required_count}")

    # Check if all required agents have completed using the counter
    if completed_count < required_count:
        print(f"[Aggregator] Waiting for {required_count - completed_count} more agents...")
        # Mark as not ready for final output
        return {"aggregation_ready": False}

    # All agents completed, extract responses
    print("[Aggregator] All agents completed, synthesizing results...")

    agent_messages = []
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and hasattr(msg, "name") and msg.name:
            agent_messages.append(f"**{msg.name}**:\n{msg.content}")

    if not agent_messages:
        print("[Aggregator] No agent responses found")
        return {"aggregation_ready": True}  # Ready to end, but no content

    # Synthesize final response
    agent_responses = "\n\n---\n\n".join(agent_messages)
    llm = get_llm(temperature=0)
    synthesis_chain = ChatPromptTemplate.from_template(AGGREGATION_PROMPT) | llm
    final_response = synthesis_chain.invoke({"agent_responses": agent_responses})

    print("[Aggregator] Synthesis complete")

    return {
        "messages": [final_response],
        "aggregation_ready": True,
    }


# ============================================================================
# PHASE 3: SELF-CORRECTION AND VALIDATION
# ============================================================================


def validate_agent_response(state: GraphState):
    """
    Validate agent responses and trigger retry if failure patterns detected.

    Failure patterns:
    - "태그를 찾을 수 없습니다" (tag not found)
    - "데이터가 없습니다" (no data)
    - "오류" (error)
    - "실패" (failed)

    Returns:
        GraphState with retry flag if needed
    """
    if not state.get("messages"):
        return {}

    last_message = state["messages"][-1]
    content = last_message.content if hasattr(last_message, "content") else ""

    # Check for failure patterns
    failure_patterns = [
        "태그를 찾을 수 없습니다",
        "데이터가 없습니다",
        "오류",
        "실패",
        "doesn't exist",
        "not found",
        "error",
    ]

    has_failure = any(pattern in content.lower() for pattern in failure_patterns)

    # Check if fuzzy suggestion was already provided
    has_suggestion = "다음 태그를 의미하셨나요?" in content or "유사한" in content

    if has_failure and not has_suggestion:
        retry_count = state.get("retry_count", 0)

        if retry_count < 2:  # Max 2 retries
            print(f"[Validator] Failure detected, retry {retry_count + 1}/2")
            return {
                "retry_count": retry_count + 1,
                "needs_retry": True,
            }
        else:
            print("[Validator] Max retries reached, accepting failure")

    return {"needs_retry": False}


# ============================================================================
# MODERN HITL WITH LANGGRAPH INTERRUPTS (LangGraph 1.x)
# ============================================================================


def execute_tool_with_approval(state: GraphState):
    """
    Execute tools with modern interrupt-based approval for write operations.

    This replaces the legacy approval workflow with LangGraph 1.x interrupt() pattern.
    When a write operation is detected, the graph pauses and waits for human approval.
    """
    from langchain_core.messages import ToolMessage
    from datetime import datetime
    import uuid

    # Get the last AI message with tool calls
    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {}

    tool_messages = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]

        print(f"[ToolNode] Executing {tool_name} with args: {tool_args}")

        # Find the tool
        tool_func = None
        for tool in chat_tools_list:
            if tool.name == tool_name:
                tool_func = tool
                break

        if not tool_func:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: Tool {tool_name} not found",
                    tool_call_id=tool_id,
                )
            )
            continue

        # Check if this is a write operation requiring approval
        is_write_operation = tool_name == "write_ignition_tag"

        if is_write_operation:
            # Create pending action
            from app.graph.state import PendingAction

            action = PendingAction(
                id=str(uuid.uuid4()),
                action_type="write_tag",
                tag_path=tool_args.get("tag_path", "unknown"),
                value=tool_args.get("value"),
                reason=f"User requested write operation via {tool_name}",
                requested_at=datetime.now(),
                status="pending",
                risk_level=_assess_risk_level(tool_args.get("tag_path", "")),
            )

            print(f"[HITL] Write operation detected: {action.tag_path} -> {action.value}")
            print(f"[HITL] Risk level: {action.risk_level}")
            print(f"[HITL] Interrupting graph for approval...")

            # Use LangGraph interrupt() to pause execution and wait for approval
            # The interrupt value will be stored in the checkpointer
            approval_request = {
                "action_id": action.id,
                "tag_path": action.tag_path,
                "value": action.value,
                "risk_level": action.risk_level,
                "requested_at": action.requested_at.isoformat(),
                "message": f"⚠️ Write operation requires approval:\n"
                          f"Tag: {action.tag_path}\n"
                          f"Value: {action.value}\n"
                          f"Risk: {action.risk_level}\n\n"
                          f"Use /api/v1/approve to approve or reject.",
            }

            # This will pause the graph and save state
            # Resume will happen via Command with human_feedback
            human_response = interrupt(approval_request)

            # When resumed, human_response will contain the approval decision
            if human_response:
                print(f"[HITL] Received approval response: {human_response}")

                if human_response.get("approved"):
                    # Execute the write operation
                    try:
                        import asyncio
                        if asyncio.iscoroutinefunction(tool_func.func):
                            result = asyncio.run(tool_func.func(**tool_args))
                        else:
                            result = tool_func.func(**tool_args)

                        tool_content = f"✅ Approved by {human_response.get('operator', 'unknown')}\n{str(result)}"
                        print(f"[HITL] Write operation executed successfully")

                    except Exception as e:
                        tool_content = f"❌ Error executing approved operation: {str(e)}"
                        print(f"[HITL] Error: {e}")
                else:
                    tool_content = f"🚫 Rejected by {human_response.get('operator', 'unknown')}\n" \
                                 f"Reason: {human_response.get('notes', 'No reason provided')}"
                    print(f"[HITL] Write operation rejected")

                tool_messages.append(
                    ToolMessage(content=tool_content, tool_call_id=tool_id)
                )
            else:
                # No response yet, should not happen but handle gracefully
                print("[HITL] Warning: Interrupt returned None")
                tool_messages.append(
                    ToolMessage(
                        content="⏸️ Awaiting approval...",
                        tool_call_id=tool_id,
                    )
                )
        else:
            # Non-write operation, execute immediately
            try:
                import asyncio
                if asyncio.iscoroutinefunction(tool_func.func):
                    result = asyncio.run(tool_func.func(**tool_args))
                else:
                    result = tool_func.func(**tool_args)

                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_id)
                )
            except Exception as e:
                print(f"[ToolNode] Error: {e}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_id,
                    )
                )

    return {"messages": tool_messages}


def _assess_risk_level(tag_path: str) -> str:
    """Assess risk level based on tag path patterns."""
    tag_lower = tag_path.lower()

    # High risk: safety-critical systems
    if any(keyword in tag_lower for keyword in ["safety", "emergency", "alarm", "trip"]):
        return "high"

    # Medium risk: actuators and control
    if any(keyword in tag_lower for keyword in ["valve", "pump", "motor", "fan", "setpoint"]):
        return "medium"

    # Low risk: indicators and displays
    return "low"


def process_human_approval(state: GraphState):
    """
    Process human approval feedback after graph resume.

    This node is called after the graph is resumed with Command.
    It extracts the approval decision from human_feedback and updates state.
    """
    feedback = state.get("human_feedback")

    if not feedback:
        print("[HITL] No human feedback found in state")
        return {}

    print(f"[HITL] Processing approval from {feedback.operator}")
    print(f"[HITL] Decision: {'APPROVED' if feedback.approved else 'REJECTED'}")

    # Create response message
    if feedback.approved:
        response = AIMessage(
            content=f"✅ **Operation Approved**\n\n"
                   f"Approved by: {feedback.operator}\n"
                   f"Time: {feedback.timestamp.isoformat()}\n"
                   f"Notes: {feedback.notes or 'None'}\n\n"
                   f"Executing operation..."
        )
    else:
        response = AIMessage(
            content=f"🚫 **Operation Rejected**\n\n"
                   f"Rejected by: {feedback.operator}\n"
                   f"Time: {feedback.timestamp.isoformat()}\n"
                   f"Reason: {feedback.notes or 'No reason provided'}"
        )

    return {
        "messages": [response],
        "human_feedback": None,  # Clear feedback after processing
    }
