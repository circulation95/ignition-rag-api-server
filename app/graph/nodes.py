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

1. 'sql_search': Questions about historical data, trends, logs, averages, past events, or database queries.
2. 'rag_search': Questions asking for definitions, manuals, troubleshooting guides, specifications, or general knowledge.
3. 'chat': Requests for real-time values, control commands, greetings, or general chat.

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


def sql_generate(state: GraphState):
    llm = ChatOllama(model=settings.llm_model_name, temperature=0)
    llm_with_tools = llm.bind_tools(sql_tools_list)

    system_msg = SystemMessage(
        content=(
            "You are an expert on Ignition Historian Databases (MariaDB).\n"
            "This database uses a specific schema where Tag Names and Data are separated.\n"
            "You must follow the Strict Execution Path below. Do NOT guess table names.\n\n"
            "### Database Structure Map\n"
            "1. `sqlth_te` table: Tag definitions.\n"
            "   - Columns: `id`, `tagpath`\n"
            "   - Usage: Query this table first to convert a Tag Name into an id.\n"
            "2. `sqlt_data_X_YYYY_MM` tables: History data (partitioned by month).\n"
            "   - Example: `sqlt_data_1_2026_01`\n"
            "   - Columns: `tagid`, `intvalue`, `floatvalue`, `t_stamp`\n"
            "   - Usage: Query this table second using the tagid from step 1.\n\n"
            "### Strict Execution Path\n"
            "When the user asks: 'Get average RPM of FAN1 on 2026-01-18':\n"
            "1. Call `db_list_tables()` to find the partition table matching the date.\n"
            "2. Call `db_query()` on `sqlth_te` to find the tag id.\n"
            "3. Call `db_query()` on the partition table to get data for the tag.\n"
            "4. Final answer: Summarize in Korean.\n\n"
            "PROHIBITED ACTIONS:\n"
            "- Never try `SELECT ... FROM FAN1`. Tag names are values, not table names.\n"
            "- Never skip `db_list_tables()`.\n"
        )
    )

    messages = [system_msg] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
