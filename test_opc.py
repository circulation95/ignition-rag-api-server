"""OPC UA endpoint discovery - IPv4 명시"""
import asyncio
from asyncua import Client

async def test():
    out = open("opc_test_result.txt", "w", encoding="utf-8")
    
    def log(msg):
        print(msg)
        out.write(msg + "\n")
        out.flush()
    
    urls = [
        "opc.tcp://127.0.0.1:62541/discovery",   # ← 권장: IPv4 명시 + Discovery 경로
        "opc.tcp://127.0.0.1:62541",
        "opc.tcp://localhost:62541/discovery",
        "opc.tcp://localhost:62541",
    ]
    
    for url in urls:
        log(f"\n=== Discovery: {url} ===")
        client = Client(url=url, timeout=5)
        try:
            endpoints = await client.connect_and_get_server_endpoints()
            log(f"Found {len(endpoints)} endpoints:")
            for i, ep in enumerate(endpoints):
                log(f"  [{i}] URL: {ep.EndpointUrl}")
                log(f"       Policy: {ep.SecurityPolicyUri}")
                log(f"       Mode: {ep.SecurityMode}")
        except Exception as e:
            log(f"FAILED: {type(e).__name__}: {e}")
    
    out.close()

asyncio.run(test())
