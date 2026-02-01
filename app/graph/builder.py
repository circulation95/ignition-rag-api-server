from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.graph.nodes import (
    generate_chat,
    generate_rag,
    intent_router,
    retrieve_rag,
    sql_generate,
)
from app.graph.state import GraphState
from app.tools import chat_tools_list, sql_tools_list


def _route_decision(state: GraphState):
    return state["intent_category"]


def build_graph():
    memory = MemorySaver()
    workflow = StateGraph(GraphState)

    workflow.add_node("intent_router", intent_router)
    workflow.add_node("retrieve_rag", retrieve_rag)
    workflow.add_node("generate_rag", generate_rag)
    workflow.add_node("generate_chat", generate_chat)
    workflow.add_node("sql_generate", sql_generate)

    workflow.add_node("chat_tools_node", ToolNode(chat_tools_list))
    workflow.add_node("sql_tools_node", ToolNode(sql_tools_list))

    workflow.add_edge(START, "intent_router")
    workflow.add_conditional_edges(
        "intent_router",
        _route_decision,
        {
            "sql_search": "sql_generate",
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

    workflow.add_conditional_edges(
        "sql_generate",
        tools_condition,
        {"tools": "sql_tools_node", END: END},
    )
    workflow.add_edge("sql_tools_node", "sql_generate")

    return workflow.compile(checkpointer=memory)
