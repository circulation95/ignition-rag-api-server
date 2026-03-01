import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Optional, Sequence
from asyncua import Client, ua

logger = logging.getLogger(__name__)

# 인증서 경로 (프로젝트 루트 기준)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CERT_PATH = _PROJECT_ROOT / "client_cert.pem"
_KEY_PATH = _PROJECT_ROOT / "client_key.pem"


class IgnitionOpcClient:
    """
    Ignition OPC UA Server 전용 클라이언트
    - Basic256Sha256 + 자체 서명 인증서 사용
    - Anonymous 또는 Username/Password 인증 지원
    - 연결 유지 + 끊기면 재연결(backoff)
    """

    def __init__(
        self,
        endpoint_url: str = "opc.tcp://127.0.0.1:62541/discovery",
        namespace_index: int = 2,
        reconnect_backoff: Sequence[float] = (0.5, 1.0, 2.0, 3.0, 5.0),
        username: str = "",
        password: str = "",
        security_policy: str = "None",
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.namespace_index = namespace_index
        self.reconnect_backoff = tuple(reconnect_backoff)
        self.username = username
        self.password = password
        self.security_policy = security_policy

        self._client: Optional[Client] = None
        self._connected: bool = False
        self._lock = asyncio.Lock()

    # -------------------------
    # Helpers
    # -------------------------
    def _normalize_tag_path(self, tag_path: str) -> str:
        # [default]TEST  -> [default]/TEST
        if "]" in tag_path and "]/" not in tag_path:
            tag_path = tag_path.replace("]", "]/", 1)
        return tag_path

    def _node_id(self, tag_path: str) -> str:
        tag_path = self._normalize_tag_path(tag_path)
        return f"ns={self.namespace_index};s={tag_path}"

    async def _connect_once(self):
        # /discovery 경로는 Endpoint 탐색 전용이므로 실제 연결 시에는 제거
        connect_url = self.endpoint_url
        if connect_url.endswith("/discovery"):
            connect_url = connect_url[: -len("/discovery")]

        client = Client(url=connect_url)

        # Username/Password가 설정된 경우 인증 정보 세팅
        if self.username:
            client.set_user(self.username)
            client.set_password(self.password)

        # 보안 정책 적용
        if self.security_policy.lower() != "none" and _CERT_PATH.exists() and _KEY_PATH.exists():
            await client.set_security_string(
                f"{self.security_policy},SignAndEncrypt,{_CERT_PATH},{_KEY_PATH}"
            )
            auth_mode = f"{self.security_policy}/User={self.username}" if self.username else f"{self.security_policy}/Anonymous"
            logger.info("OPC UA connecting with %s...", auth_mode)
        else:
            # Security=None / Anonymous 모드
            logger.info("Security=None / Anonymous 모드로 연결합니다.")

        await client.connect()
        self._client = client
        self._connected = True
        logger.info("✅ OPC UA connected to %s", connect_url)

    async def _connect_with_retries(self):
        last_err: Optional[Exception] = None
        for delay in (0.0, *self.reconnect_backoff):
            if delay:
                await asyncio.sleep(delay)
            try:
                await self._connect_once()
                return
            except Exception as e:
                last_err = e
                logger.warning("OPC UA connect failed (will retry): %s", e)

        raise RuntimeError(f"Failed to connect to OPC UA server: {last_err}") from last_err

    # -------------------------
    # Public
    # -------------------------
    async def connect(self):
        async with self._lock:
            if self._connected and self._client:
                return
            await self._connect_with_retries()

    async def disconnect(self):
        async with self._lock:
            if self._client:
                try:
                    await self._client.disconnect()
                finally:
                    self._client = None
                    self._connected = False
                    logger.info("🔌 OPC UA disconnected")

    async def _ensure(self):
        if not (self._connected and self._client):
            await self.connect()

    async def read_tag(self, tag_path: str) -> dict:
        await self._ensure()
        node_id = self._node_id(tag_path)

        try:
            node = self._client.get_node(node_id)
            dv = await node.read_data_value()

            return {
                "tag": tag_path,
                "nodeId": node_id,
                "value": dv.Value.Value,
                "status": dv.StatusCode.name,
            }

        except Exception as e:
            # 끊김이면 다음 호출에서 자동 재연결되도록 상태를 내려둠
            async with self._lock:
                self._connected = False
                self._client = None
            return {"tag": tag_path, "nodeId": node_id, "error": str(e)}

    async def write_tag(self, tag_path: str, value: Any) -> dict:
        await self._ensure()
        node_id = self._node_id(tag_path)

        try:
            node = self._client.get_node(node_id)

            # 타입 맞춰서 쓰기 (VariantType 유지)
            dv = await node.read_data_value()
            vtype = dv.Value.VariantType

            # 필요 시 기본 캐스팅 (문자 -> 숫자)
            cur = dv.Value.Value
            if isinstance(cur, bool):
                if isinstance(value, str):
                    value = value.strip().lower() in ("1", "true", "yes", "on")
                else:
                    value = bool(value)
            elif isinstance(cur, int) and not isinstance(value, int):
                value = int(value)
            elif isinstance(cur, float) and not isinstance(value, float):
                value = float(value)

            await node.write_value(ua.Variant(value, vtype))

            return {"tag": tag_path, "nodeId": node_id, "written": value, "status": "OK"}

        except Exception as e:
            async with self._lock:
                self._connected = False
                self._client = None
            return {"tag": tag_path, "nodeId": node_id, "error": str(e)}

    async def _get_tags_namespace_index(self) -> int:
        """Ignition 태그 네임스페이스 인덱스를 동적으로 조회"""
        tag_uri = "urn:inductiveautomation:ignition:opcua:tags"
        try:
            idx = await self._client.get_namespace_index(tag_uri)
            logger.debug("Ignition tags namespace index: %d", idx)
            return idx
        except Exception:
            logger.warning("Could not resolve tags namespace URI, using default index=%d", self.namespace_index)
            return self.namespace_index

    async def get_all_tags(self, provider: str = "[default]") -> list[dict]:
        """
        Ignition의 지정된 Tag Provider 아래 전체 태그를 재귀적으로 검색합니다.
        
        Args:
            provider: 검색할 Tag Provider (예: "[default]")
            
        Returns:
            list[dict]: 검색된 태그 목록 (tag_path, display_name, description, tag_type)
        """
        await self._ensure()
        try:
            # 네임스페이스 인덱스를 URI로 동적 조회
            ns_idx = await self._get_tags_namespace_index()
            
            # Ignition 태그 루트 노드 접근 (예: ns=2;s=[default])
            root_node_id = f"ns={ns_idx};s={provider}"
            root_node = self._client.get_node(root_node_id)
            
            # 직접 browse 시도
            children = await root_node.get_children()
            logger.info("Tag provider root '%s' has %d children (ns=%d)", provider, len(children), ns_idx)
            
            if children:
                tags = await self._browse_tags(root_node, path=provider, ns_idx=ns_idx)
                logger.info("OPC UA browse completed: found %d tags under %s", len(tags), provider)
                return tags
            
            # fallback: Objects 노드 아래에서 해당 ns 노드 검색
            logger.warning(
                "'%s' (ns=%d) has no children. Trying fallback browse from Objects node...",
                provider, ns_idx
            )
            objects_node = self._client.get_node("i=85")
            obj_children = await objects_node.get_children()
            all_tags = []
            for obj in obj_children:
                if obj.nodeid.NamespaceIndex == ns_idx:
                    bname = await obj.read_browse_name()
                    sub_tags = await self._browse_tags(obj, path=f"{provider}/{bname.Name}", ns_idx=ns_idx)
                    all_tags.extend(sub_tags)
            
            if all_tags:
                logger.info("Fallback browse found %d tags", len(all_tags))
            else:
                logger.warning(
                    "No tags found via any browse strategy. "
                    "Ignition Gateway에서 Tag Provider OPC UA 노출이 활성화됐는지 확인하세요."
                )
            return all_tags
            
        except Exception as e:
            logger.error("Failed to browse tags under %s: %s", provider, e)
            return []

    async def _browse_tags(self, node, path: str = "", ns_idx: int = 2) -> list[dict]:
        """주어진 노드 아래를 재귀적으로 탐색하여 Variable 노드를 태그로 반환"""
        tags = []
        try:
            children = await node.get_children()
            
            for child in children:
                try:
                    bname = await child.read_browse_name()
                    name = bname.Name
                    node_class = await child.read_node_class()
                    
                    # Ignition 태그 경로 구성: [default]TagName 또는 [default]/Folder/TagName
                    if path.endswith("]"):
                        current_path = f"{path}{name}"
                    else:
                        current_path = f"{path}/{name}"
                    
                    if node_class == ua.NodeClass.Variable:
                        try:
                            dv = await child.read_data_value()
                            tag_type = dv.Value.VariantType.name if dv.Value.VariantType else "Unknown"
                            tags.append({
                                "tag_path": current_path,
                                "display_name": name,
                                "description": "",
                                "tag_type": tag_type
                            })
                        except Exception as inner_e:
                            logger.debug("Failed to read variable %s: %s", current_path, inner_e)
                    
                    elif node_class in (ua.NodeClass.Object, ua.NodeClass.ObjectType):
                        sub_tags = await self._browse_tags(child, current_path, ns_idx=ns_idx)
                        tags.extend(sub_tags)
                        
                except Exception as e:
                    logger.debug("Failed to read child node: %s", e)
                    
        except Exception as e:
            logger.debug("Failed to get children for %s: %s", path, e)
            
        return tags
