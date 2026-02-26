import uuid
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from app.graph.state import PendingAction
from app.services.opc import get_opc_client
from app.services.tag_store import ingest_tags


def assess_risk(tag_path: str, value: Any) -> str:
    """
    Assess risk level based on tag type.

    High risk: Motors, valves, pumps, emergency systems, safety systems
    Medium risk: Setpoints, alarms, enables
    Low risk: Display values, non-critical tags
    """
    critical_keywords = [
        "motor",
        "valve",
        "pump",
        "emergency",
        "safety",
        "fan",
        "compressor",
    ]
    medium_keywords = ["setpoint", "alarm", "enable", "mode"]

    tag_lower = tag_path.lower()

    if any(kw in tag_lower for kw in critical_keywords):
        return "high"
    elif any(kw in tag_lower for kw in medium_keywords):
        return "medium"
    return "low"


@tool
async def read_ignition_tag(tag_path: str):
    """
    Ignition SCADA tag value read.

    Args:
        tag_path: Full tag path (e.g. "[default]Tank/Temperature")
    """
    opc_client = get_opc_client()
    print(f"[Tool] Read tag: {tag_path}")
    return await opc_client.read_tag(tag_path)


@tool
def write_ignition_tag(tag_path: str, value: str):
    """
    Request to write value to Ignition SCADA tag.

    IMPORTANT: This operation requires human approval for safety.
    A PendingAction will be created and must be approved via /approve endpoint.

    Args:
        tag_path: Full tag path (e.g. "[default]Tank/Setpoint")
        value: Value to write (string or number)

    Returns:
        Approval request message with action ID and risk level
    """
    # Generate unique action ID
    action_id = str(uuid.uuid4())

    # Assess risk level
    risk_level = assess_risk(tag_path, value)

    # Create pending action (will be stored in GraphState by agent)
    pending_action = PendingAction(
        id=action_id,
        action_type="write_tag",
        tag_path=tag_path,
        value=value,
        reason=f"User requested write operation to {tag_path}",
        requested_at=datetime.now(),
        status="pending",
        risk_level=risk_level,
    )

    print(f"[Tool] Write operation queued for approval: {tag_path} -> {value}")
    print(f"[Tool] Action ID: {action_id}, Risk: {risk_level}")

    # Return pending action info (agent will extract and store in state)
    return {
        "status": "pending_approval",
        "action_id": action_id,
        "tag_path": tag_path,
        "value": value,
        "risk_level": risk_level,
        "message": f"⚠️ Write operation requires approval:\n"
        f"Tag: {tag_path}\n"
        f"Value: {value}\n"
        f"Risk Level: {risk_level}\n"
        f"Action ID: {action_id}\n"
        f"Use POST /api/v1/approve with action_id to approve.",
        "_pending_action": pending_action,  # Internal field for state storage
    }


@tool
async def sync_ignition_tags_to_vector_store(provider: str = "[default]") -> str:
    """
    Ignition SCADA 태그 정보를 벡터 스토어(ChromaDB)와 동기화합니다.
    사용자가 '태그 동기화해줘', '태그 정보 업데이트해줘' 라고 할 때 사용합니다.
    
    Args:
        provider: 검색할 Tag Provider (기본값: "[default]")
        
    Returns:
        동기화 결과 요약 문자열
    """
    opc_client = get_opc_client()
    print(f"[Tool] Syncing tags from OPC UA provider: {provider}")
    
    try:
        tags = await opc_client.get_all_tags(provider=provider)
        if not tags:
            return f"Error: No tags found under provider '{provider}'."
            
        indexed_count = ingest_tags(tags)
        return f"Successfully synchronized {indexed_count} tags from {provider} to the vector store."
    except Exception as e:
        return f"Error occurred during tag synchronization: {e}"


chat_tools_list = [read_ignition_tag, write_ignition_tag, sync_ignition_tags_to_vector_store]
