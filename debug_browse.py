"""OPC UA Browse - ns=2 태그 노출 확인 (기존 서버 OPC 클라이언트 재사용)"""
import asyncio
from asyncua import Client, ua

ENDPOINT = "opc.tcp://127.0.0.1:62541"

async def main():
    # 기존 uvicorn 서버가 OPC 세션을 잡고 있으므로
    # 별도 클라이언트로 접속 (Ignition은 다중 세션 허용)
    client = Client(url=ENDPOINT, timeout=30)
    try:
        await client.connect()
        print("✅ Connected")
        ns_array = await client.get_namespace_array()
        print(f"Namespaces: {ns_array}")
        
        # ns=2 인덱스 확인
        ns2_uri = "urn:inductiveautomation:ignition:opcua:tags"
        try:
            ns2_idx = await client.get_namespace_index(ns2_uri)
            print(f"Tags namespace index: {ns2_idx}")
        except Exception as e:
            print(f"ns lookup failed: {e}")
            ns2_idx = 2

        # [default] 노드 직접 시도
        for ns_idx in [ns2_idx, 1, 2, 3]:
            for path in ["[default]", "default", "Tag Providers/default"]:
                node_id = f"ns={ns_idx};s={path}"
                try:
                    node = client.get_node(node_id)
                    children = await node.get_children()
                    print(f"✅ {node_id} → {len(children)} children")
                    for c in children[:5]:
                        bname = await c.read_browse_name()
                        nc = await c.read_node_class()
                        print(f"   [{nc.name}] {bname.Name!r}  id={c.nodeid.Identifier!r}")
                except Exception as e:
                    print(f"❌ {node_id} → {e}")

        # Objects 아래에서 ns=2 노드 찾기
        print("\n=== Objects 아래 ns=2 노드 ===")
        objects = client.get_node("i=85")
        children = await objects.get_children()
        for c in children:
            if c.nodeid.NamespaceIndex == ns2_idx:
                bname = await c.read_browse_name()
                nc = await c.read_node_class()
                print(f"  ns={ns2_idx} [{nc.name}] {bname.Name!r} id={c.nodeid.Identifier!r}")
                sub = await c.get_children()
                for s in sub[:5]:
                    bname2 = await s.read_browse_name()
                    nc2 = await s.read_node_class()
                    print(f"    ns={s.nodeid.NamespaceIndex} [{nc2.name}] {bname2.Name!r} id={s.nodeid.Identifier!r}")

    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        try:
            await client.disconnect()
        except:
            pass

asyncio.run(main())
