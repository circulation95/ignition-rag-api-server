from app.core.config import settings
from app.opc_client import IgnitionOpcClient


_opc_client = IgnitionOpcClient(
    endpoint_url=settings.opc_endpoint,
    username=settings.opc_username,
    password=settings.opc_password,
    security_policy=settings.opc_security_policy,
)


def get_opc_client() -> IgnitionOpcClient:
    return _opc_client
