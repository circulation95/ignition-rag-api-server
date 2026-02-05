# Ignition RAG API Server

Ignition SCADA 시스템을 위한 LangGraph 기반 AI 에이전트 API 서버입니다.

사용자의 자연어 질문을 분석하여 **실시간 태그 조회**, **히스토리 데이터 검색**, **알람 이력 조회**, **문서 기반 RAG** 중 적절한 경로로 라우팅하고 응답을 생성합니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| **Intent Router** | LLM이 질문을 분석하여 적절한 처리 경로 선택 |
| **OPC UA 연동** | Ignition 태그 실시간 읽기/쓰기 |
| **Tag History** | 최적화된 태그 히스토리 데이터 조회 |
| **Alarm History** | 알람 이벤트 이력 및 통계 조회 |
| **RAG 검색** | Chroma 벡터스토어 기반 문서 검색 |
| **대화 메모리** | thread_id 기반 세션별 대화 히스토리 유지 |

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        POST /ask                                │
│                            │                                    │
│                            ▼                                    │
│                    ┌──────────────┐                             │
│                    │Intent Router │                             │
│                    └──────┬───────┘                             │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                   │
│         ▼                 ▼                 ▼                   │
│   ┌───────────┐    ┌────────────┐    ┌────────────┐             │
│   │sql_search │    │rag_search  │    │   chat     │             │
│   └─────┬─────┘    └─────┬──────┘    └─────┬──────┘             │
│         │                │                 │                    │
│         ▼                ▼                 ▼                    │
│   ┌───────────┐    ┌────────────┐    ┌────────────┐             │
│   │Tag History│    │   Chroma   │    │ OPC Tools  │             │
│   │Alarm Tools│    │ Retriever  │    │ (Ignition) │             │
│   │ (MariaDB) │    └────────────┘    └────────────┘             │
│   └───────────┘                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Intent 분류 기준

| Intent | 트리거 조건 | 예시 |
|--------|-------------|------|
| `sql_search` | 과거 데이터, 트렌드, 평균, 로그, **알람 이력** | "어제 FAN1 평균 RPM은?", "FAN1 알람 언제 발생했어?" |
| `rag_search` | 정의, 매뉴얼, 스펙, 트러블슈팅, 알람코드 의미 | "PID 제어란 무엇인가요?", "알람 코드 E001 의미는?" |
| `chat` | 실시간 값, 제어 명령, 일반 대화 | "현재 Tank1 온도 알려줘", "FAN1 켜줘" |

## 설치

### 요구사항

- Python 3.11+
- Poetry
- Ollama (LLM 서버)
- MariaDB (Ignition Historian)
- OPC UA Server (Ignition)

### 설치 방법

```bash
# 저장소 클론
git clone <repository-url>
cd rag-api-server

# Poetry로 의존성 설치
poetry install

# 또는 pip 사용
pip install -r requirements.txt
```

## 설정

### 환경 변수 (.env)

```env
# 앱 설정
APP_NAME=Ignition Agent
ENV=dev
DEBUG=false

# LLM 설정
LLM_MODEL_NAME=qwen3:8b

# 임베딩 설정
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-large
EMBEDDING_DEVICE=cuda
EMBEDDING_NORMALIZE=true

# Chroma 벡터스토어 설정
VECTORSTORE_PATH=./chroma_db
VECTORSTORE_K=5
CHROMA_COLLECTION_NAME=ignition_docs

# OPC UA 설정
OPC_ENDPOINT=opc.tcp://localhost:62541

# MariaDB 설정
SQL_HOST=127.0.0.1
SQL_PORT=3306
SQL_USER=ignition
SQL_PASSWORD=password
SQL_DB=ignition
```

## 실행

```bash
# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 또는
python -m app.main
```

## API 사용법

### POST /ask

질문을 보내고 AI 응답을 받습니다.

**Request:**

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "현재 Tank1 온도가 몇 도야?",
    "thread_id": "user_123"
  }'
```

**Request Body:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `question` | string | O* | 질문 내용 |
| `query` | string | O* | `question`의 별칭 |
| `thread_id` | string | X | 세션 ID (기본값: `default_user`) |

> *`question` 또는 `query` 중 하나는 필수

**Response:**

```json
{
  "intent": "chat",
  "answer": "현재 Tank1의 온도는 32.5°C입니다."
}
```

| 필드 | 설명 |
|------|------|
| `intent` | 분류된 의도 (`chat`, `sql_search`, `rag_search`) |
| `answer` | AI 생성 응답 |

### 질문 예시

```bash
# 실시간 태그 조회 (chat)
"현재 Tank1 온도 알려줘"
"FAN1 켜줘"

# 태그 히스토리 조회 (sql_search)
"2025년 9월 1일 FAN1 평균 RPM은?"
"어제 Tank1 최고 온도는?"

# 알람 이력 조회 (sql_search)
"FAN1 알람이 최근에 언제 발생했어?"
"지난주 Smoke 알람 통계 알려줘"

# 문서 검색 (rag_search)
"PID 제어란 무엇인가요?"
"알람 코드 E001 의미는?"
```

### GET /health

서버 상태 확인

```bash
curl http://localhost:8000/health
```

## 프로젝트 구조

```
rag-api-server/
├── app/
│   ├── main.py                  # FastAPI 앱 진입점
│   ├── api/
│   │   └── v1/
│   │       ├── router.py        # API 라우터 설정
│   │       ├── ask.py           # /ask 엔드포인트
│   │       └── health.py        # /health 엔드포인트
│   ├── core/
│   │   └── config.py            # 설정 관리 (Pydantic Settings)
│   ├── graph/
│   │   ├── builder.py           # LangGraph 워크플로우 빌드
│   │   ├── nodes.py             # 그래프 노드 함수들
│   │   └── state.py             # GraphState 정의
│   ├── tools/
│   │   ├── opc_tools.py         # OPC UA 도구 (태그 읽기/쓰기)
│   │   ├── sql_tools.py         # SQL 도구 (레거시)
│   │   ├── tag_history_tools.py # 태그 히스토리 도구 (최적화)
│   │   └── alarm_tools.py       # 알람 이력 도구
│   └── services/
│       ├── vectorstore.py       # Chroma 벡터스토어 관리
│       ├── sql.py               # MariaDB 연결 관리
│       └── opc.py               # OPC UA 클라이언트 관리
├── tests/
├── chroma_db/                   # Chroma 벡터스토어 데이터
├── pyproject.toml               # Poetry 설정
├── requirements.txt
└── README.md
```

## 도구 (Tools)

### OPC Tools (chat 경로)

| 도구 | 설명 |
|------|------|
| `read_ignition_tag(tag_path)` | Ignition 태그 값 읽기 |
| `write_ignition_tag(tag_path, value)` | Ignition 태그 값 쓰기 |

**태그 경로 예시:** `[default]Tank/Temperature`

### Tag History Tools (sql_search 경로)

| 도구 | 설명 |
|------|------|
| `parse_date_to_partition(date_string)` | 자연어 날짜를 파티션 정보로 변환 |
| `find_partition_table(year, month)` | 파티션 테이블 존재 여부 확인 |
| `get_tag_id(tag_name)` | 태그명으로 ID 조회 |
| `get_tag_history(tag_id, year, month, ...)` | 히스토리 데이터 직접 조회 |

**Ignition Historian 스키마:**

- `sqlth_te`: 태그 정의 (`id`, `tagpath`)
- `sqlt_data_X_YYYY_MM`: 히스토리 데이터 (월별 파티션)

### Alarm Tools (sql_search 경로)

| 도구 | 설명 |
|------|------|
| `get_latest_alarm_for_tag(tag_name)` | 특정 태그의 최근 알람 조회 |
| `search_alarm_events(tag_name, hours_ago, ...)` | 알람 이벤트 검색 |
| `get_alarm_statistics(tag_name, days)` | 알람 통계 조회 |
| `get_alarm_count_by_period(tag_name, start_date, end_date)` | 기간별 알람 횟수 |

**alarm_events 테이블:**

- `eventtime`: 알람 발생 시간 (Unix timestamp ms)
- `source`: 알람 소스 (형식: `prov:default:/tag:경로:/alm:ALARM`)
- `eventtype`: 0=Active, 1=Clear, 2=Acknowledged

## 기술 스택

- **Framework:** FastAPI
- **AI/LLM:** LangChain, LangGraph, Ollama
- **Vector Store:** Chroma
- **Embedding:** HuggingFace (multilingual-e5-large)
- **Database:** MariaDB (SQLAlchemy)
- **OPC UA:** asyncua
