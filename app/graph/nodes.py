from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.core.config import settings
from app.graph.state import GraphState
from app.services.vectorstore import get_retriever
from app.tools import chat_tools_list, sql_tools_list


def intent_router(state: GraphState):
    print("[Router] Intent classification...")
    question = state["messages"][-1].content

    llm = ChatOllama(model=settings.llm_model_name, temperature=0, format="json")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a smart router. Classify the user question into one of three categories:

1. 'sql_search': Questions about historical/past data, trends, logs, averages, statistics, or database queries.
   - Keywords: 평균, 최대, 최소, 합계, 트렌드, 로그, 기록, 히스토리, 과거, 어제, 지난주, 특정 날짜
   - Examples:
     - "2026년 1월 18일 FAN1 평균 RPM은?" → sql_search
     - "어제 Tank1 최고 온도는?" → sql_search
     - "지난주 펌프 가동 시간은?" → sql_search

2. 'rag_search': Questions asking for definitions, manuals, troubleshooting guides, specifications, or general knowledge.
   - Keywords: 무엇, 정의, 매뉴얼, 가이드, 스펙, 사양, 에러코드, 알람코드, 설명
   - Examples:
     - "PID 제어란 무엇인가요?" → rag_search
     - "알람 코드 E001 의미는?" → rag_search

3. 'chat': Requests for CURRENT/real-time values, control commands, greetings, or general chat.
   - Keywords: 현재, 지금, 실시간, 켜줘, 꺼줘, 설정해줘, 안녕
   - Examples:
     - "현재 Tank1 온도 알려줘" → chat
     - "FAN1 켜줘" → chat

IMPORTANT: If a specific date/time is mentioned (like "2026년 1월 18일", "어제", "지난주"), it is ALWAYS 'sql_search'.

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


SQL_AGENT_PROMPT = """You are an expert on Ignition Historian Databases (MariaDB).
This database uses a specific schema where Tag Names and Data are separated.

### Database Structure Map
1. `sqlth_te` table: Tag definitions.
   - Columns: `id`, `tagpath`
   - Usage: Query this table first to convert a Tag Name into an id.
2. `sqlt_data_X_YYYY_MM` tables: History data (partitioned by month).
   - Example: `sqlt_data_1_2026_01`
   - Columns: `tagid`, `intvalue`, `floatvalue`, `t_stamp`
   - Usage: Query this table second using the tagid from step 1.

### Think Step-by-Step (ReAct Pattern)
When the user asks for historical data (e.g., 'Get average RPM of FAN1 on 2026-01-18'):

**Step 1 - Discover Tables:**
- Think: "I need to find which partition table exists for this date"
- Action: Call `db_list_tables()` to list all tables
- Observe: Look for `sqlt_data_X_YYYY_MM` pattern matching the date

**Step 2 - Find Tag ID:**
- Think: "I need to convert the tag name to an id"
- Action: Call `db_query()` with `SELECT id, tagpath FROM sqlth_te WHERE tagpath LIKE '%FAN1%'`
- Observe: Note the tag id from the result

**Step 3 - Query Data:**
- Think: "Now I can query the actual data using the tag id"
- Action: Call `db_query()` on the partition table with the tag id
- Observe: Analyze the results

**Step 4 - Respond:**
- Summarize the findings in Korean

### PROHIBITED ACTIONS
- Never try `SELECT ... FROM FAN1`. Tag names are values, not table names.
- Never skip `db_list_tables()` - always verify table existence first.
- Never guess table names without checking.

Answer in Korean."""


def build_sql_react_agent():
    """SQL 전용 ReAct Agent 생성"""
    llm = ChatOllama(model=settings.llm_model_name, temperature=0)
    return create_react_agent(
        model=llm,
        tools=sql_tools_list,
        prompt=SQL_AGENT_PROMPT,
    )


# ReAct Agent 인스턴스 (서브그래프로 사용)
sql_react_agent = build_sql_react_agent()
