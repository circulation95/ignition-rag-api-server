from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama

from app.core.config import settings
from app.graph.state import GraphState
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

    llm = ChatOllama(model=settings.llm_model_name, temperature=0, format="json")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a smart router. Classify the user question into one of three categories:

1. 'sql_search': Questions about historical/past data, trends, logs, averages, statistics, database queries, OR ALARM HISTORY.
   - Keywords: 평균, 최대, 최소, 합계, 트렌드, 로그, 기록, 히스토리, 과거, 어제, 지난주, 특정 날짜
   - Alarm Keywords: 알람, 경보, 발생, 언제, alarm, 알람 이력, 알람 기록, 최근 알람
   - Examples:
     - "2026년 1월 18일 FAN1 평균 RPM은?" → sql_search
     - "어제 Tank1 최고 온도는?" → sql_search
     - "FAN1 알람이 최근에 언제 발생했어?" → sql_search
     - "지난주 Smoke 알람 몇 번 발생했어?" → sql_search
     - "알람 통계 보여줘" → sql_search

2. 'rag_search': Questions asking for definitions, manuals, troubleshooting guides, specifications, or general knowledge.
   - Keywords: 무엇, 정의, 매뉴얼, 가이드, 스펙, 사양, 에러코드, 알람코드 의미, 설명
   - Examples:
     - "PID 제어란 무엇인가요?" → rag_search
     - "알람 코드 E001 의미는?" → rag_search (알람 코드의 '의미'를 묻는 것)

3. 'chat': Requests for CURRENT/real-time values, control commands, greetings, or general chat.
   - Keywords: 현재, 지금, 실시간, 켜줘, 꺼줘, 설정해줘, 안녕
   - Examples:
     - "현재 Tank1 온도 알려줘" → chat
     - "FAN1 켜줘" → chat

IMPORTANT:
- If a specific date/time is mentioned (like "2026년 1월 18일", "어제", "지난주"), it is ALWAYS 'sql_search'.
- If asking about alarm occurrence, history, or statistics → 'sql_search'
- If asking about alarm code meaning/definition → 'rag_search'

Return ONLY a JSON object: {"destination": "sql_search" | "rag_search" | "chat"}
""",
            ),
            ("human", "{question}"),
        ]
    )

    chain = prompt | llm | JsonOutputParser()

    try:
        result = chain.invoke({"question": question})
        destination = result.get("destination", "chat")
    except Exception:
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
    llm = ChatOllama(model=settings.llm_model_name, temperature=0.1)
    llm_with_tools = llm.bind_tools(chat_tools_list)
    system_msg = SystemMessage(
        content="You are an Ignition SCADA Operator. Answer in Korean."
    )
    response = llm_with_tools.invoke([system_msg] + state["messages"])
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

5. `get_latest_alarm_for_tag(tag_name)`: 특정 태그의 최근 알람 조회
   - "FAN1 알람 언제 발생?" → get_latest_alarm_for_tag("FAN1")

6. `search_alarm_events(tag_name, hours_ago, event_type, limit)`: 알람 이벤트 검색
   - tag_name: 태그명 (선택)
   - hours_ago: 최근 N시간 (기본 24)
   - event_type: "active", "clear", "ack" (선택)

7. `get_alarm_statistics(tag_name, days)`: 알람 통계 조회
   - 발생 횟수, 태그별 분포

8. `get_alarm_count_by_period(tag_name, start_date, end_date)`: 기간별 알람 횟수
   - start_date, end_date: "YYYY-MM-DD" 형식

## Workflow Examples

### 태그 히스토리 조회
Q: "2025년 9월 1일 FAN1 평균 RPM은?"
1. parse_date_to_partition("2025년 9월 1일") → year=2025, month=9, day=1
2. get_tag_id("FAN1") → id=5
3. get_tag_history(5, 2025, 9, 1, 1, "avg") → avg_value=1234.5

### 알람 조회
Q: "FAN1 알람이 최근에 언제 발생했어?"
1. get_latest_alarm_for_tag("FAN1") → eventtime, source 정보

Q: "지난주 Smoke 알람 통계 알려줘"
1. get_alarm_statistics("Smoke", 7) → 발생 횟수, 분포

Answer in Korean. 숫자와 시간 정보를 명확하게 전달하세요."""


def build_sql_react_agent():
    """SQL 전용 ReAct Agent 생성 (태그 히스토리 + 알람 도구)"""
    llm = ChatOllama(model=settings.llm_model_name, temperature=0)
    # 태그 히스토리 도구 + 알람 도구 결합
    combined_tools = tag_history_tools_list + alarm_tools_list
    return create_react_agent(
        model=llm,
        tools=combined_tools,
        prompt=SQL_AGENT_PROMPT,
    )


# ReAct Agent 인스턴스 (서브그래프로 사용)
sql_react_agent = build_sql_react_agent()


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

    llm = ChatOllama(model=settings.llm_model_name, temperature=0, format="json")

    supervisor_chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system", SUPERVISOR_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        | llm
        | JsonOutputParser()
    )

    try:
        result = supervisor_chain.invoke({"messages": state["messages"]})
        required_agents = result.get("required_agents", [])
        reasoning = result.get("reasoning", "")

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

    llm = ChatOllama(model=settings.llm_model_name, temperature=0)
    llm_with_tools = llm.bind_tools(chat_tools_list)

    agent_chain = ChatPromptTemplate.from_messages(
        [
            ("system", OPERATIONS_AGENT_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    ) | llm_with_tools

    response = agent_chain.invoke({"messages": state["messages"]})

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

    Uses ReAct pattern for multi-step reasoning with tag history tools.
    """
    print("[Historian Agent] Analyzing historical data...")

    llm = ChatOllama(model=settings.llm_model_name, temperature=0)

    # Create ReAct agent with specialized historian prompt
    historian_react_agent = create_react_agent(
        model=llm,
        tools=tag_history_tools_list,
        state_modifier=SystemMessage(content=HISTORIAN_AGENT_PROMPT),
    )

    # Execute agent
    result = historian_react_agent.invoke(state)

    # Extract the final message and mark with agent name
    if result.get("messages"):
        final_msg = result["messages"][-1]
        if isinstance(final_msg, AIMessage):
            final_msg.name = "Historian Agent"

        # Increment parallel execution counter
        completed = state.get("agents_completed", 0) + 1

        return {
            "messages": [final_msg],
            "agents_completed": completed,
        }

    # Increment counter even if no message (agent failed)
    return {"agents_completed": state.get("agents_completed", 0) + 1}


def alarm_agent(state: GraphState):
    """
    Handle alarm event correlation and analysis.

    Uses alarm tools to identify patterns and root causes.
    """
    print("[Alarm Agent] Analyzing alarm events...")

    llm = ChatOllama(model=settings.llm_model_name, temperature=0)

    # Create ReAct agent with specialized alarm prompt
    alarm_react_agent = create_react_agent(
        model=llm,
        tools=alarm_tools_list,
        state_modifier=SystemMessage(content=ALARM_AGENT_PROMPT),
    )

    # Execute agent
    result = alarm_react_agent.invoke(state)

    # Extract the final message and mark with agent name
    if result.get("messages"):
        final_msg = result["messages"][-1]
        if isinstance(final_msg, AIMessage):
            final_msg.name = "Alarm Agent"

        # Increment parallel execution counter
        completed = state.get("agents_completed", 0) + 1

        return {
            "messages": [final_msg],
            "agents_completed": completed,
        }

    # Increment counter even if no message (agent failed)
    return {"agents_completed": state.get("agents_completed", 0) + 1}


def knowledge_agent(state: GraphState):
    """
    Handle documentation and troubleshooting search.

    Uses RAG retrieval for contextual information.
    """
    print("[Knowledge Agent] Searching documentation...")

    # Retrieve documents
    retriever = get_retriever()
    if not retriever:
        return {}

    query = state["payload"]
    docs = retriever.invoke(query)

    # Generate response with context
    llm = ChatOllama(model=settings.llm_model_name, temperature=0)

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
    llm = ChatOllama(model=settings.llm_model_name, temperature=0)
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
