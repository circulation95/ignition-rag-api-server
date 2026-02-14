from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


@dataclass
class PendingAction:
    """Represents a write operation pending human approval."""

    id: str  # UUID
    action_type: Literal["write_tag"]
    tag_path: str
    value: Any
    reason: str
    requested_at: datetime
    status: Literal["pending", "approved", "rejected", "executed"]
    risk_level: Literal["low", "medium", "high"]


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    intent_category: str
    payload: str
    documents: List[Document]
    pending_actions: Optional[List[PendingAction]]  # Phase 1: Approval workflow
    required_agents: Optional[List[str]]  # Phase 2: For supervisor routing
    agent_results: Optional[Dict[str, Any]]  # Phase 2: Store results from each agent
    retry_count: Optional[int]  # Phase 3: For self-correction
    agents_completed: Optional[int]  # Phase 3: Parallel execution barrier
    aggregation_ready: Optional[bool]  # Phase 3: Flag for final aggregation
