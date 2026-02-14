from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


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
    operator: Optional[str] = None  # Who approved/rejected
    notes: Optional[str] = None  # Approval/rejection notes
    approved_at: Optional[datetime] = None  # When approved/rejected


@dataclass
class HumanFeedback:
    """Human feedback for graph interrupts (LangGraph 1.x HITL pattern)."""

    action_id: str
    approved: bool
    operator: str
    notes: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# ============================================================================
# Structured Output Models (for LLM responses)
# ============================================================================


class IntentRouterOutput(BaseModel):
    """Structured output for intent router."""

    destination: Literal["sql_search", "rag_search", "chat"] = Field(
        description="The category to route the user query to"
    )


class SupervisorRouterOutput(BaseModel):
    """Structured output for supervisor router."""

    required_agents: List[Literal["operations", "historian", "alarm", "knowledge"]] = Field(
        description="List of agents required to handle the query"
    )
    reasoning: str = Field(
        description="Explanation of why these agents are needed"
    )


class GraphState(TypedDict):
    messages: List[BaseMessage]  # Removed add_messages reducer for stateless mode
    intent_category: str
    payload: str
    documents: List[Document]

    # Phase 1: Approval workflow (Legacy - being refactored)
    pending_actions: Optional[List[PendingAction]]

    # Phase 1.5: Modern HITL with LangGraph interrupts
    current_action: Optional[PendingAction]  # Single action awaiting approval
    human_feedback: Optional[HumanFeedback]  # Feedback from interrupt resume
    interrupt_reason: Optional[str]  # Why the graph was interrupted

    # Phase 2: For supervisor routing
    required_agents: Optional[List[str]]
    agent_results: Optional[Dict[str, Any]]  # Store results from each agent

    # Phase 3: For self-correction and parallel execution
    retry_count: Optional[int]
    agents_completed: Optional[int]  # Parallel execution barrier
    aggregation_ready: Optional[bool]  # Flag for final aggregation
