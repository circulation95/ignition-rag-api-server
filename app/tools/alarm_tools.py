"""Alarm History 조회 도구"""

import re
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

from app.services.sql import get_sql_db


def extract_tag_from_source(source: str) -> str:
    """
    source 컬럼에서 태그명 추출.
    형식: "prov:default:/tag:BMS/MFD/8F/ELEC1-SA-MFD-1/Smoke_Detect_Alm:/alm:ALARM"
    추출: "/tag:" 와 ":/alm:" 사이 값
    """
    match = re.search(r"/tag:(.+?):/alm:", source)
    if match:
        return match.group(1)
    return source


def format_timestamp(ts_ms: int) -> str:
    """밀리초 타임스탬프를 읽기 쉬운 형식으로 변환"""
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts_ms)


@tool
def get_latest_alarm_for_tag(tag_path: Optional[str] = None) -> str:
    """
    특정 태그의 가장 최근 알람 조회. tag_path를 지정하지 않으면 전체 태그 중 가장 최근 알람을 반환.

    Args:
        tag_path: 태그 경로 (예: "FAN1", "Smoke_Detect", "Motor") - 부분 일치 검색. None이면 전체 조회.

    Returns:
        가장 최근 알람 정보 (발생 시간, 태그, 상태)
    """
    if tag_path:
        where_clause = f"WHERE source LIKE '%{tag_path}%'"
        not_found_msg = f"'{tag_path}' 관련 알람 기록이 없습니다."
    else:
        where_clause = ""
        not_found_msg = "알람 기록이 없습니다."

    query = f"""
    SELECT
        eventtime,
        source,
        displaypath,
        priority,
        eventtype
    FROM alarm_events
    {where_clause}
    ORDER BY eventtime DESC
    LIMIT 1
    """

    try:
        result = get_sql_db().run(query)
        if not result or result == "[]" or result == "":
            return not_found_msg

        return f"최근 알람 조회 결과:\n{result}"
    except Exception as e:
        return f"알람 조회 오류: {e}"


@tool
def search_alarm_events(
    tag_path: Optional[str] = None,
    hours_ago: int = 24,
    event_type: Optional[str] = None,
    limit: int = 50,
) -> str:
    """
    알람 이벤트 검색.

    Args:
        tag_path: 태그 경로 검색어 (예: "FAN1", "Tank") - 부분 일치, None이면 전체
        hours_ago: 최근 N시간 내 조회 (기본 24시간)
        event_type: "active", "clear", "ack" 또는 None (전체)
        limit: 최대 반환 행 수 (기본 50)

    Returns:
        알람 이벤트 목록
    """
    # 시간 범위 계산
    start_dt = datetime.now() - timedelta(hours=hours_ago)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    # WHERE 조건 구성
    conditions = [f"eventtime >= '{start_str}'"]

    if tag_path:
        conditions.append(f"source LIKE '%{tag_path}%'")

    if event_type:
        event_type_map = {"active": 0, "clear": 1, "ack": 2, "acknowledged": 2}
        if event_type.lower() in event_type_map:
            conditions.append(f"eventtype = {event_type_map[event_type.lower()]}")

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT
        eventtime,
        source,
        displaypath,
        priority,
        eventtype
    FROM alarm_events
    WHERE {where_clause}
    ORDER BY eventtime DESC
    LIMIT {limit}
    """

    try:
        result = get_sql_db().run(query)
        if not result or result == "[]" or result == "":
            filter_desc = f"태그: {tag_path}, " if tag_path else ""
            return f"조건에 맞는 알람이 없습니다. ({filter_desc}최근 {hours_ago}시간)"
        return f"알람 이벤트 조회 결과 (최근 {hours_ago}시간):\n{result}"
    except Exception as e:
        return f"알람 검색 오류: {e}"


@tool
def get_alarm_statistics(tag_path: Optional[str] = None, days: int = 7) -> str:
    """
    알람 통계 조회 (발생 횟수, 태그별 분포).

    Args:
        tag_path: 태그 경로 필터 (선택, 부분 일치)
        days: 최근 N일 (기본 7일)

    Returns:
        알람 통계 정보
    """
    start_dt = datetime.now() - timedelta(days=days)
    start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    tag_filter = f"AND source LIKE '%{tag_path}%'" if tag_path else ""

    query = f"""
    SELECT
        source,
        COUNT(*) as alarm_count,
        SUM(CASE WHEN eventtype = 0 THEN 1 ELSE 0 END) as active_count,
        SUM(CASE WHEN eventtype = 1 THEN 1 ELSE 0 END) as clear_count,
        MIN(eventtime) as first_alarm,
        MAX(eventtime) as last_alarm
    FROM alarm_events
    WHERE eventtime >= '{start_str}' {tag_filter}
    GROUP BY source
    ORDER BY alarm_count DESC
    LIMIT 20
    """

    try:
        result = get_sql_db().run(query)
        if not result or result == "[]" or result == "":
            return f"최근 {days}일간 알람 기록이 없습니다."
        return f"알람 통계 (최근 {days}일):\n{result}"
    except Exception as e:
        return f"알람 통계 조회 오류: {e}"


@tool
def get_alarm_count_by_period(
    tag_path: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    특정 기간의 알람 발생 횟수 조회.

    Args:
        tag_path: 태그 경로 필터 (선택)
        start_date: 시작 날짜 "YYYY-MM-DD" (선택, 기본 7일 전)
        end_date: 종료 날짜 "YYYY-MM-DD" (선택, 기본 오늘)

    Returns:
        기간별 알람 발생 횟수
    """
    today = datetime.now()

    # 날짜 파싱
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return f"날짜 형식 오류: {start_date}. YYYY-MM-DD 형식을 사용하세요."
    else:
        start_dt = today - timedelta(days=7)

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            return f"날짜 형식 오류: {end_date}. YYYY-MM-DD 형식을 사용하세요."
    else:
        end_dt = today

    start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    tag_filter = f"AND source LIKE '%{tag_path}%'" if tag_path else ""

    query = f"""
    SELECT
        COUNT(*) as total_alarms,
        SUM(CASE WHEN eventtype = 0 THEN 1 ELSE 0 END) as active_count,
        SUM(CASE WHEN eventtype = 1 THEN 1 ELSE 0 END) as clear_count,
        SUM(CASE WHEN eventtype = 2 THEN 1 ELSE 0 END) as ack_count
    FROM alarm_events
    WHERE eventtime >= '{start_str}' AND eventtime <= '{end_str}' {tag_filter}
    """

    try:
        result = get_sql_db().run(query)
        period_str = f"{start_dt.strftime('%Y-%m-%d')} ~ {end_dt.strftime('%Y-%m-%d')}"
        if tag_path:
            return f"'{tag_path}' 알람 통계 ({period_str}):\n{result}"
        return f"전체 알람 통계 ({period_str}):\n{result}"
    except Exception as e:
        return f"알람 횟수 조회 오류: {e}"


alarm_tools_list = [
    get_latest_alarm_for_tag,
    search_alarm_events,
    get_alarm_statistics,
    get_alarm_count_by_period,
]
