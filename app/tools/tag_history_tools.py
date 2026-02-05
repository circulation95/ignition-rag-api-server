"""Tag History 전용 도구 - SQL 성능 최적화"""

import re
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

from app.services.sql import get_sql_db


@tool
def parse_date_to_partition(date_string: str) -> str:
    """
    자연어 날짜를 파티션 테이블 정보로 변환.

    Args:
        date_string: "2025년 9월 1일", "2025-09-01", "어제", "오늘" 등

    Returns:
        year, month, day 및 예상 테이블명 정보
    """
    today = datetime.now()

    # 상대적 날짜 처리
    if "어제" in date_string:
        target = today - timedelta(days=1)
    elif "오늘" in date_string:
        target = today
    elif "그제" in date_string or "그저께" in date_string:
        target = today - timedelta(days=2)
    elif "지난주" in date_string:
        target = today - timedelta(weeks=1)
    elif "지난달" in date_string:
        target = today - timedelta(days=30)
    else:
        # "2025년 9월 1일" 패턴
        match = re.search(r"(\d{4})년?\s*(\d{1,2})월?\s*(\d{1,2})일?", date_string)
        if match:
            target = datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3))
            )
        else:
            # "2025-09-01" 패턴
            match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_string)
            if match:
                target = datetime(
                    int(match.group(1)), int(match.group(2)), int(match.group(3))
                )
            else:
                # "9월 1일" 패턴 (연도 생략 - 현재 연도 가정)
                match = re.search(r"(\d{1,2})월?\s*(\d{1,2})일?", date_string)
                if match:
                    target = datetime(today.year, int(match.group(1)), int(match.group(2)))
                else:
                    return f"날짜 파싱 실패: {date_string}. 예시: '2025년 9월 1일', '어제'"

    return (
        f"year={target.year}, month={target.month}, day={target.day}, "
        f"expected_table=sqlt_data_1_{target.year}_{target.month:02d}"
    )


@tool
def find_partition_table(year: int, month: int) -> str:
    """
    해당 연월의 파티션 테이블명 찾기.
    sqlt_data_1, sqlt_data_2 등 여러 인덱스를 확인하여 존재하는 테이블 반환.

    Args:
        year: 연도 (예: 2025)
        month: 월 (1-12)

    Returns:
        존재하는 파티션 테이블명 또는 에러 메시지
    """
    try:
        all_tables = get_sql_db().get_table_names()
        pattern = f"sqlt_data_{{}}_{year}_{month:02d}"

        found_tables = []
        for idx in range(1, 10):  # 1~9까지 확인
            table_name = pattern.format(idx)
            if table_name in all_tables:
                found_tables.append(table_name)

        if found_tables:
            return f"발견된 테이블: {', '.join(found_tables)}"
        else:
            return f"해당 월({year}-{month:02d})의 파티션 테이블이 없습니다."
    except Exception as e:
        return f"테이블 검색 오류: {e}"


@tool
def get_tag_id(tag_name: str) -> str:
    """
    sqlth_te 테이블에서 태그명으로 ID 조회.

    Args:
        tag_name: 태그명 (예: "FAN1", "Tank1_Temperature") - 부분 일치 검색

    Returns:
        태그 ID와 전체 tagpath 정보
    """
    query = f"""
    SELECT id, tagpath
    FROM sqlth_te
    WHERE tagpath LIKE '%{tag_name}%'
    LIMIT 10
    """
    try:
        result = get_sql_db().run(query)
        if not result or result == "[]":
            return f"'{tag_name}'와 일치하는 태그를 찾을 수 없습니다."
        return result
    except Exception as e:
        return f"태그 조회 오류: {e}"


@tool
def get_tag_history(
    tag_id: int,
    year: int,
    month: int,
    start_day: Optional[int] = None,
    end_day: Optional[int] = None,
    aggregation: str = "raw",
    limit: int = 1000,
) -> str:
    """
    태그 히스토리 데이터 조회. 파티션 테이블 직접 지정.

    Args:
        tag_id: sqlth_te에서 조회한 태그 ID
        year: 연도 (예: 2025)
        month: 월 (1-12)
        start_day: 시작일 (선택, 미지정시 월 전체)
        end_day: 종료일 (선택)
        aggregation: "raw", "avg", "max", "min", "sum", "count" 중 선택
        limit: 최대 반환 행 수 (기본 1000, raw 모드에서만 적용)

    Returns:
        히스토리 데이터 또는 집계 결과
    """
    # 파티션 테이블명 생성 (기본 인덱스 1)
    table_name = f"sqlt_data_1_{year}_{month:02d}"

    # 날짜 범위 조건 생성 (t_stamp는 밀리초 단위)
    where_parts = [f"tagid = {tag_id}"]

    if start_day:
        start_ts = int(datetime(year, month, start_day).timestamp() * 1000)
        where_parts.append(f"t_stamp >= {start_ts}")
    if end_day:
        end_ts = int(datetime(year, month, end_day, 23, 59, 59).timestamp() * 1000)
        where_parts.append(f"t_stamp <= {end_ts}")

    where_clause = " AND ".join(where_parts)

    # 집계 쿼리 생성
    if aggregation == "raw":
        query = f"""
        SELECT t_stamp, floatvalue, intvalue
        FROM {table_name}
        WHERE {where_clause}
        ORDER BY t_stamp DESC
        LIMIT {limit}
        """
    elif aggregation in ("avg", "max", "min", "sum", "count"):
        agg_func = aggregation.upper()
        if aggregation == "count":
            select_expr = "COUNT(*) as count_value"
        else:
            select_expr = f"{agg_func}(COALESCE(floatvalue, intvalue)) as {aggregation}_value"

        query = f"""
        SELECT
            {select_expr},
            COUNT(*) as data_count,
            MIN(t_stamp) as first_ts,
            MAX(t_stamp) as last_ts
        FROM {table_name}
        WHERE {where_clause}
        """
    else:
        return f"지원하지 않는 집계 함수: {aggregation}. 사용 가능: raw, avg, max, min, sum, count"

    try:
        result = get_sql_db().run(query)
        if not result or result == "[]":
            return f"데이터가 없습니다. (테이블: {table_name}, tagid: {tag_id})"
        return result
    except Exception as e:
        error_msg = str(e)
        if "doesn't exist" in error_msg or "Table" in error_msg:
            return (
                f"테이블 {table_name}이 존재하지 않습니다. "
                f"find_partition_table({year}, {month})로 실제 테이블명을 확인하세요."
            )
        return f"쿼리 오류: {e}"


tag_history_tools_list = [
    parse_date_to_partition,
    find_partition_table,
    get_tag_id,
    get_tag_history,
]
