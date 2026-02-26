"""IgnitionOpcClient 전체 기능 테스트 - No Security / Anonymous"""
import asyncio
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))
# Windows cp949 인코딩 문제 방지
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from app.opc_client import IgnitionOpcClient


async def main():
    results = open("test_full_result.txt", "w", encoding="utf-8")

    def log(msg):
        print(msg)
        results.write(msg + "\n")
        results.flush()

    # No Security + Anonymous
    client = IgnitionOpcClient(
        endpoint_url="opc.tcp://127.0.0.1:62541",
        namespace_index=2,
    )

    log("=" * 60)
    log("1) 연결 테스트")
    log("=" * 60)
    try:
        await client.connect()
        log("[OK] 연결 성공!")
    except Exception as e:
        log(f"[FAIL] 연결 실패: {type(e).__name__}: {e}")
        results.close()
        return

    log("")
    log("=" * 60)
    log("2) 태그 탐색 (Browse)")
    log("=" * 60)
    tags = []
    try:
        tags = await client.get_all_tags("[default]")
        if tags:
            log(f"[OK] {len(tags)}개 태그 발견:")
            for t in tags[:20]:
                log(f"   - {t['tag_path']}  (type={t['tag_type']})")
            if len(tags) > 20:
                log(f"   ... 외 {len(tags) - 20}개")
        else:
            log("[WARN] [default] 프로바이더에 태그가 없습니다.")
    except Exception as e:
        log(f"[FAIL] 태그 탐색 실패: {type(e).__name__}: {e}")

    log("")
    log("=" * 60)
    log("3) 태그 읽기 테스트")
    log("=" * 60)
    if tags:
        first_tag = tags[0]["tag_path"]
        log(f"   대상 태그: {first_tag}")
        result = await client.read_tag(first_tag)
        if "error" in result:
            log(f"[FAIL] 읽기 실패: {result['error']}")
        else:
            log(f"[OK] 값: {result['value']}  (상태: {result['status']})")
    else:
        log("[SKIP] 읽을 태그가 없어 스킵합니다.")

    log("")
    log("=" * 60)
    log("4) 연결 종료")
    log("=" * 60)
    await client.disconnect()
    log("[OK] 정상 종료")
    results.close()


asyncio.run(main())
