from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.graph.nodes import (
    generate_chat,
    generate_rag,
    intent_router,
    retrieve_rag,
    sql_react_agent,
)
from app.graph.state import GraphState
from app.tools import chat_tools_list


def _route_decision(state: GraphState):
    return state["intent_category"]


def build_graph():
    memory = MemorySaver()
    workflow = StateGraph(GraphState)

    workflow.add_node("intent_router", intent_router)
    workflow.add_node("retrieve_rag", retrieve_rag)
    workflow.add_node("generate_rag", generate_rag)
    workflow.add_node("generate_chat", generate_chat)

    # SQL ReAct Agent를 서브그래프로 추가
    # create_react_agent는 자체적으로 도구 호출 루프를 관리
    workflow.add_node("sql_react_agent", sql_react_agent)

    workflow.add_node("chat_tools_node", ToolNode(chat_tools_list))

    workflow.add_edge(START, "intent_router")
    workflow.add_conditional_edges(
        "intent_router",
        _route_decision,
        {
            "sql_search": "sql_react_agent",
            "rag_search": "retrieve_rag",
            "chat": "generate_chat",
        },
    )

    workflow.add_edge("retrieve_rag", "generate_rag")
    workflow.add_edge("generate_rag", END)

    workflow.add_conditional_edges(
        "generate_chat",
        tools_condition,
        {"tools": "chat_tools_node", END: END},
    )
    workflow.add_edge("chat_tools_node", "generate_chat")

    # ReAct Agent는 자체 루프가 있으므로 직접 END로 연결
    workflow.add_edge("sql_react_agent", END)

    return workflow.compile(checkpointer=memory)
