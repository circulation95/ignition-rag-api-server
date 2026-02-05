from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.core.config import settings
from app.graph.state import GraphState
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
