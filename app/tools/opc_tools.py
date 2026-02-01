from langchain_core.tools import tool

from app.services.opc import get_opc_client


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
async def write_ignition_tag(tag_path: str, value: str):
    """
    Ignition SCADA tag value write.

    Args:
        tag_path: Full tag path (e.g. "[default]Tank/Setpoint")
        value: Value to write (string or number)
    """
    opc_client = get_opc_client()
    print(f"[Tool] Write tag: {tag_path} -> {value}")
    return await opc_client.write_tag(tag_path, value)


chat_tools_list = [read_ignition_tag, write_ignition_tag]
