from typing import Annotated, List, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    intent_category: str
    payload: str
    documents: List[Document]
