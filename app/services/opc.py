from app.core.config import settings
from app.opc_client import IgnitionOpcClient


_opc_client = IgnitionOpcClient(settings.opc_endpoint)


def get_opc_client() -> IgnitionOpcClient:
    return _opc_client
