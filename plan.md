# Ignition RAG Chatbot 서버 리팩토링 계획

## 개요
- **목표**: SQL Tag History 성능 개선 + Alarm History 기능 추가 + 벡터스토어 전환
- **현재 아키텍처**: LangGraph 기반 3경로 라우팅 (sql_search, rag_search, chat)

---

## Phase 1: SQL Tag History 성능 개선 (우선순위: 높음)

### 문제점
현재 ReAct Agent가 매번 `db_list_tables()` 호출 후 LLM이 테이블명을 추론하는 방식으로 불필요한 지연 발생

### 해결책: 전용 태그 히스토리 도구 추가

#### 1.1 새 파일 생성: `app/tools/tag_history_tools.py`

```python
@tool
def parse_date_to_partition(date_string: str) -> str:
    """자연어 날짜 → 파티션 테이블 정보 변환"""
    # "2025년 9월 1일" → year=2025, month=9, table=sqlt_data_1_2025_09

@tool
def get_tag_id(tag_name: str) -> str:
    """sqlth_te에서 태그명으로 ID 조회 (LIMIT 10)"""

@tool
def get_tag_history(tag_id, year, month, start_day, end_day, aggregation, limit) -> str:
    """파티션 테이블 직접 쿼리 (sqlt_data_X_YYYY_MM)"""
    # 참고: X는 보통 1이지만 2, 3 등일 수 있음 → 테이블 존재 여부 확인 로직 포함

@tool
def find_partition_table(year: int, month: int) -> str:
    """해당 월의 파티션 테이블명 찾기 (sqlt_data_1, 2, 3... 중 존재하는 것)"""
```

#### 1.2 수정 파일: `app/graph/nodes.py`
- `SQL_AGENT_PROMPT` 간소화 (새 도구 사용법으로 변경)
- `build_sql_react_agent()` 도구 목록 교체
- 91-143줄 영역 수정

#### 1.3 수정 파일: `app/tools/__init__.py`
- `tag_history_tools_list` export 추가

---

## Phase 2: Alarm History 조회 기능 추가 (우선순위: 높음)

### 구현 내용

#### 2.1 새 파일 생성: `app/tools/alarm_tools.py`

```python
@tool
def get_latest_alarm_for_tag(tag_name: str) -> str:
    """특정 태그의 최근 알람 조회"""
    # source 컬럼에서 /tag:..../alm 사이 값 파싱
    # eventtime 타임스탬프 반환

@tool
def search_alarm_events(tag_name, hours_ago, event_type, limit) -> str:
    """알람 이벤트 검색"""

@tool
def get_alarm_statistics(tag_name, days) -> str:
    """알람 통계 (발생 횟수, 우선순위별)"""
```

#### 2.2 수정 파일: `app/graph/nodes.py`
- Intent Router 프롬프트에 알람 키워드 추가 (22-45줄)
  - "알람", "경보", "발생", "언제" → sql_search로 분류
- SQL Agent 도구 목록에 alarm_tools 추가

#### 2.3 alarm_events 테이블 구조 (확인됨)
```sql
-- source 컬럼 형식: "prov:default:/tag:BMS/MFD/8F/ELEC1-SA-MFD-1/Smoke_Detect_Alm:/alm:ALARM"
-- 태그명 추출: "/tag:" 와 ":/alm:" 사이 값
-- 예: /tag:BMS/MFD/8F/ELEC1-SA-MFD-1/Smoke_Detect_Alm:/alm: → 태그명: BMS/MFD/8F/ELEC1-SA-MFD-1/Smoke_Detect_Alm

def extract_tag_from_source(source: str) -> str:
    match = re.search(r'/tag:(.+?):/alm:', source)
    return match.group(1) if match else source
```

---

## Phase 3: FAISS → Chroma 전환 (우선순위: 중간 - 포함 확정)

### 현재 상태
- FAISS IndexFlatL2 + InMemoryDocstore
- 파일: `app/services/vectorstore.py`

### Chroma 장점
- 메타데이터 필터링 지원
- 자동 영속성 (PersistentClient)
- HNSW 인덱스 (대규모 데이터에 유리)

### 전환 시 수정 파일
- `app/services/vectorstore.py` (전체 재작성)
- `app/core/config.py` (vectorstore_path 변경)
- `pyproject.toml` / `requirements.txt` (langchain-chroma, chromadb 추가)

---

## 수정 파일 요약

| 파일 | 작업 | Phase |
|------|------|-------|
| `app/tools/tag_history_tools.py` | **신규 생성** | 1 |
| `app/tools/alarm_tools.py` | **신규 생성** | 2 |
| `app/tools/__init__.py` | export 추가 | 1, 2 |
| `app/graph/nodes.py` | 프롬프트 + 도구 수정 | 1, 2 |
| `app/services/vectorstore.py` | Chroma 전환 | 3 |
| `app/core/config.py` | vectorstore_path 변경 | 3 |

---

## 검증 방법

### Phase 1 테스트
```
Q: "2025년 9월 1일 FAN1 평균 RPM은?"
예상: parse_date → get_tag_id → get_tag_history(aggregation="avg")
```

### Phase 2 테스트
```
Q: "FAN1 알람이 최근에 언제 발생했어?"
예상: get_latest_alarm_for_tag("FAN1") → eventtime 반환
```

### Phase 3 테스트
```
Q: RAG 검색 쿼리 실행 후 Chroma 인덱스 정상 작동 확인
```

---

## 확인된 사항 (사용자 답변)
1. **파티션 인덱스**: 거의 1이지만 테이블 꼬임 시 2, 3 등 증가 가능 → 동적 테이블 탐색 필요
2. **alarm_events source 형식**: `prov:default:/tag:BMS/MFD/.../Smoke_Detect_Alm:/alm:ALARM`
   - 태그명 추출: `/tag:` 와 `:/alm:` 사이 값
3. **Chroma 전환**: 포함하기로 확정

---

## 구현 순서

1. **Phase 1**: `tag_history_tools.py` 생성 + `nodes.py` 수정 → SQL 성능 개선 ✅
2. **Phase 2**: `alarm_tools.py` 생성 + Intent Router 수정 → 알람 조회 기능 ✅
3. **Phase 3**: `vectorstore.py` Chroma 전환 + 의존성 추가 ✅

---

## 완료된 변경 사항

### 신규 파일
- `app/tools/tag_history_tools.py` - 태그 히스토리 전용 도구 4개
- `app/tools/alarm_tools.py` - 알람 조회 도구 4개

### 수정된 파일
- `app/graph/nodes.py` - Intent Router 알람 키워드 추가, SQL Agent 프롬프트 최적화
- `app/tools/__init__.py` - 새 도구 export 추가
- `app/services/vectorstore.py` - FAISS → Chroma 전환
- `app/core/config.py` - vectorstore_path, chroma_collection_name 추가
