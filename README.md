# Ignition SCADA AI 에이전트 - RAG API 서버

**Ignition SCADA 운영, 분석, 트러블슈팅을 위한 지능형 멀티 에이전트 시스템**

이 시스템은 RAG(검색 증강 생성), 실시간 운영 제어, 히스토리 데이터 분석을 활용하여 Ignition SCADA 시스템에 대한 지능형 쿼리 처리를 제공하는 Supervisor 기반 멀티 에이전트 아키텍처의 API 서버입니다.

## 🌟 주요 기능

### 🔐 Phase 1: 안전 우선 운영 (Legacy)
- **사람-기계 협업(Human-in-the-Loop) 승인**: 모든 쓰기 작업은 실행 전 명시적 승인 필요
- **위험도 평가**: 작업의 자동 분류 (high/medium/low 위험도)
- **감사 추적(Audit Trail)**: 운영자 신원과 함께 모든 승인 결정 완전 기록
- **승인 워크플로우**: 대기 중인 작업 관리를 위한 RESTful 엔드포인트

### 🧠 Phase 2: Supervisor 멀티 에이전트 아키텍처
- **지능형 쿼리 라우팅**: 단순/복잡 쿼리 자동 감지
- **5개의 전문 에이전트**:
  - **Supervisor Agent**: 복잡한 다중 도메인 쿼리 조율
  - **Operations Agent**: 안전 제어를 갖춘 실시간 태그 읽기/쓰기
  - **Historian Agent**: ReAct 추론을 활용한 복잡한 시계열 분석
  - **Alarm Agent**: 이벤트 상관관계 및 근본 원인 분석
  - **Knowledge Agent**: RAG 기반 문서 검색
- **Fast Path 최적화**: 단순 쿼리는 Supervisor 오버헤드 우회
- **결과 종합**: 다중 에이전트 발견 사항의 일관된 집계

## 📊 아키텍처 개요

```
사용자 쿼리
    ↓
Intent Router (복잡도 감지)
    ↓
    ├─ 단순 쿼리 (Fast Path)
    │   ├─ Operations (실시간 태그)
    │   ├─ SQL Search (히스토리 데이터)
    │   └─ RAG Search (문서)
    │
    └─ 복잡 쿼리 (Supervisor Path)
        ↓
    Supervisor Agent (작업 분해)
        ↓
    ┌────────────── 병렬 실행 ──────────────┐
    │                                        │
    ├─ Operations Agent    (실시간 값)     ┤
    ├─ Historian Agent     (통계 분석)     ┤
    ├─ Alarm Agent         (이벤트 상관)   ┤
    └─ Knowledge Agent     (문서)          ┘
        ↓
    집계 및 종합
        ↓
    최종 응답
```

## 🛠️ 기술 스택

- **프레임워크**: FastAPI (고성능을 위한 async/await)
- **AI/LLM**: Ollama와 함께하는 LangChain + LangGraph 1.x (로컬 qwen3:8b 모델)
- **오케스트레이션**: 병렬 실행을 위한 Send API를 갖춘 LangGraph StateGraph
- **HITL Pattern**: LangGraph interrupt()/Command API (LangGraph 1.x)
- **State Persistence**: SqliteSaver checkpointer (서버 재시작 시에도 상태 유지)
- **벡터 스토어**: Chroma (RAG 문서 검색)
- **데이터베이스**: 파티션된 히스토리안 테이블을 갖춘 MariaDB
- **SCADA 통합**: Ignition 태그 작업을 위한 OPC UA 프로토콜

## 📦 설치

### 사전 요구사항

```bash
# Python 3.10+
python --version

# Ollama (로컬 LLM용)
ollama --version

# MariaDB
mysql --version
```

### 설치 절차

1. **저장소 클론**
```bash
git clone <repository-url>
cd rag-api-server
```

2. **의존성 설치**
```bash
pip install -r requirements.txt
```

3. **LLM 모델 다운로드**
```bash
ollama pull qwen3:8b
```

4. **환경 설정**
```bash
cp .env.example .env
# .env 파일을 편집하여 설정 입력
```

5. **벡터 스토어 초기화** (선택사항 - RAG용)
```bash
# 문서를 data/documents/에 배치
python scripts/init_vectorstore.py
```

6. **서버 실행**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🔧 설정

### 환경 변수

```bash
# LLM 설정
LLM_MODEL_NAME=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434

# 데이터베이스 설정
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/ignition
SQL_PROMPT_DIALECT=MariaDB

# OPC 설정
OPC_SERVER_URL=opc.tcp://localhost:62541

# 벡터 스토어
CHROMA_PERSIST_DIRECTORY=./data/chroma_db
EMBEDDING_MODEL=nomic-embed-text
```

## 📡 API 엔드포인트

### 1. Ask 엔드포인트 (메인 쿼리 인터페이스)

**POST** `/api/v1/ask`

AI 에이전트 시스템에 쿼리 제출

**요청:**
```json
{
  "question": "현재 알람을 분석해줘",
  "thread_id": "user_session_123"
}
```

**응답:**
```json
{
  "intent": "supervisor",
  "answer": "**현재 알람 분석**\n\n**알람 정보:**\n- Tag: Tank1/Temperature\n- 발생 시간: 2026-02-14 14:30:00\n- 우선순위: High\n\n**현재 값:** 95°C\n**과거 평균:** 75°C\n**원인 분석:** 열교환기 오염 가능성\n\n**조치 사항:**\n1. 열교환기 점검\n2. 냉각수 유량 확인"
}
```

**승인 대기 중인 응답 (Modern HITL):**
```json
{
  "intent": "chat",
  "status": "pending_approval",
  "answer": "⚠️ 쓰기 작업은 승인이 필요합니다...",
  "thread_id": "user_session_123",
  "pending_action": {
    "action_id": "abc-123-def-456",
    "tag_path": "[default]FAN/FAN1",
    "value": 0,
    "risk_level": "high",
    "message": "Write operation requires approval...",
    "approval_url": "/api/v1/approve",
    "state_url": "/api/v1/state/user_session_123",
    "requested_at": "2026-02-14T14:30:00"
  }
}
```

### 2. 승인 엔드포인트

**POST** `/api/v1/approve`

대기 중인 쓰기 작업 승인 또는 거부 (Modern HITL - LangGraph Command API)

**요청:**
```json
{
  "thread_id": "user_session_123",
  "action_id": "abc-123-def-456",
  "approved": true,
  "operator": "홍길동",
  "notes": "유지보수를 위해 승인됨"
}
```

> **Note**: Modern HITL 패턴에서는 `thread_id`가 필수입니다. 이를 통해 중단된 그래프 상태를 찾아 재개합니다.

**응답:**
```json
{
  "status": "executed",
  "action_id": "abc-123-def-456",
  "message": "쓰기 작업이 성공적으로 실행되었습니다",
  "result": {
    "tag_path": "[default]FAN/FAN1",
    "value": 0,
    "executed_at": "2026-02-14T14:35:00",
    "operator": "홍길동"
  }
}
```

**GET** `/api/v1/pending`

모든 승인 대기 작업 목록 조회

**응답:**
```json
{
  "count": 2,
  "actions": [
    {
      "id": "abc-123",
      "tag_path": "[default]FAN/FAN1",
      "value": 0,
      "risk_level": "high",
      "requested_at": "2026-02-14T14:30:00",
      "reason": "사용자가 쓰기 작업을 요청함"
    }
  ]
}
```

**GET** `/api/v1/state/{thread_id}`

특정 스레드의 현재 상태 조회 (디버깅용)

**응답:**
```json
{
  "thread_id": "user_session_123",
  "next": ["chat_tools_node"],
  "tasks": [{"id": "task_001", "name": "execute_tool_with_approval"}],
  "checkpoint_id": "1a2b3c4d",
  "values_keys": ["messages", "intent_category", "current_action"]
}
```

### 3. 헬스 체크

**GET** `/api/v1/health`

API 서버 상태 확인

## 🎯 쿼리 예시

### 단순 쿼리 (Fast Path)

**실시간 운영:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Tank1 온도는?",
    "thread_id": "session_1"
  }'
```

**히스토리 데이터:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "FAN1 어제 히스토리 보여줘",
    "thread_id": "session_2"
  }'
```

**문서 검색:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "열교환기 점검 절차는?",
    "thread_id": "session_3"
  }'
```

### 복잡 쿼리 (Supervisor 멀티 에이전트)

**알람 분석:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "현재 알람을 분석하고 원인을 찾아줘",
    "thread_id": "session_4"
  }'
```
*트리거: Alarm Agent + Operations Agent + Historian Agent + Knowledge Agent (병렬)*

**트렌드 조사:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Tank1 온도 비정상 원인 조사",
    "thread_id": "session_5"
  }'
```
*트리거: Operations Agent + Historian Agent + Knowledge Agent (병렬)*

**트러블슈팅:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "FAN1 고장 진단 및 트러블슈팅",
    "thread_id": "session_6"
  }'
```
*트리거: 4개 에이전트 모두 병렬 실행*

### 제어 작업 (승인 필요)

**쓰기 작업:**
```bash
# 1단계: 쓰기 작업 요청
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "FAN1을 꺼줘",
    "thread_id": "session_7"
  }'

# 응답에 pending_action.id 포함됨

# 2단계: 작업 승인
curl -X POST http://localhost:8000/api/v1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "action_id": "abc-123-def-456",
    "approved": true,
    "operator": "홍길동"
  }'
```

## 🧪 테스트

### 병렬 실행 테스트

서버 로그에서 병렬 실행 지표 확인:

```bash
# 로그에서 다음 패턴 확인:
[Supervisor] Required agents: ['alarm', 'operations', 'historian']
[Router] Dispatching to alarm (parallel)
[Router] Dispatching to operations (parallel)
[Router] Dispatching to historian (parallel)
[Alarm Agent] Analyzing alarm events...
[Operations Agent] Processing real-time operations...    # ← 동시 실행
[Historian Agent] Analyzing historical data...           # ← 동시 실행
[Aggregator] Agent completion: 3/3
[Aggregator] All agents completed, synthesizing results...
```

### 퍼지 매칭 테스트

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Tan1 온도 히스토리",
    "thread_id": "fuzzy_test"
  }'

# 예상 결과: "Tank1/Temperature", "Tank2/Temperature" 제안
```

### 승인 워크플로우 테스트

```bash
# 1. 대기 중인 작업 목록 조회
curl http://localhost:8000/api/v1/pending

# 2. 작업 거부
curl -X POST http://localhost:8000/api/v1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "action_id": "abc-123",
    "approved": false,
    "operator": "김철수",
    "notes": "운영 중에는 권한 없음"
  }'
```

## 📚 에이전트 역할

### Supervisor Agent
- 쿼리 복잡도 분석
- 필요한 전문 에이전트 결정
- 복잡한 작업을 하위 작업으로 분해
- 다중 에이전트 결과 종합

### Operations Agent
- 실시간 태그 값 읽기
- 쓰기 작업에 대한 승인 요청 생성
- 태그 경로 검증
- 비정상 값 보고

### Historian Agent
- 히스토리 시계열 데이터 검색
- 통계 분석 수행 (평균, 최대, 최소, 트렌드)
- 현재 값과 과거 기준값 비교
- 이상 징후 및 패턴 식별

### Alarm Agent
- 태그/시간/유형별 알람 이벤트 검색
- 알람과 태그 값 변화 상관관계 분석
- 알람 빈도 및 패턴 식별
- 근본 원인 힌트 제공

### Knowledge Agent
- 문서 및 매뉴얼 검색
- 알람 코드 및 오류 메시지 설명
- 단계별 절차 제공
- "무엇", "어떻게" 질문에 답변

## 🔍 쿼리 복잡도 감지

쿼리는 키워드를 기반으로 자동으로 **단순** 또는 **복잡**으로 분류됩니다:

**복잡 쿼리 키워드:**
- 분석 (analyze)
- 비교 (compare)
- 원인 (cause)
- 조사 (investigate)
- 트러블슈팅 (troubleshooting)
- 진단 (diagnose)
- 검증 (verify)

**라우팅:**
- **복잡** → Supervisor → 멀티 에이전트 (병렬 실행)
- **단순** → Fast Path (단일 에이전트, 최소 지연)

## 📈 성능 벤치마크

### 병렬 실행 속도 향상

**3개 에이전트 쿼리 예시:**
- 순차 실행 (Phase 2): 6초
- 병렬 실행 (Phase 3): 3초
- **속도 향상: 50%** ⚡

**4개 에이전트 복잡 쿼리:**
- 순차 실행: 8초
- 병렬 실행: 4초
- **속도 향상: 50%** ⚡

### 쿼리 응답 시간

| 쿼리 유형 | Fast Path | Supervisor (순차) | Supervisor (병렬) |
|-----------|-----------|------------------|------------------|
| 단순 읽기 | <1초 | N/A | N/A |
| 히스토리 쿼리 | 1-2초 | N/A | N/A |
| 2개 에이전트 복잡 | N/A | 4초 | 2초 |
| 3개 에이전트 복잡 | N/A | 6초 | 3초 |
| 4개 에이전트 복잡 | N/A | 8초 | 4초 |

## 🛡️ 안전 기능

1. **직접 실행 금지**: 쓰기 작업은 즉시 실행되지 않음
2. **위험도 평가**: 태그 유형에 따른 자동 분류
3. **승인 필수**: 모든 쓰기 작업은 사람의 승인 필요
4. **감사 로깅**: 누가 무엇을 언제 승인했는지 완전한 기록
5. **타임아웃**: 대기 중인 작업은 설정 가능한 기간 후 만료
6. **운영자 신원**: 모든 승인은 운영자 이름과 함께 기록

## 🔄 개발 워크플로우

### 프로젝트 구조

```
rag-api-server/
├── app/
│   ├── api/v1/          # API 엔드포인트
│   │   ├── ask.py       # 메인 쿼리 엔드포인트
│   │   ├── approve.py   # 승인 워크플로우
│   │   └── router.py    # API 라우터
│   ├── graph/           # LangGraph 워크플로우
│   │   ├── builder.py   # 그래프 구성
│   │   ├── nodes.py     # 에이전트 구현
│   │   ├── prompts.py   # 전문 에이전트 프롬프트
│   │   └── state.py     # 상태 정의
│   ├── tools/           # 에이전트 도구
│   │   ├── opc_tools.py        # 태그 읽기/쓰기
│   │   ├── tag_history_tools.py # 히스토리 쿼리
│   │   └── alarm_tools.py      # 알람 검색
│   ├── services/        # 핵심 서비스
│   │   ├── opc.py              # OPC UA 클라이언트
│   │   ├── sql.py              # 데이터베이스 클라이언트
│   │   ├── vectorstore.py      # Chroma RAG
│   │   └── approval_storage.py # 대기 중인 작업
│   └── core/
│       └── config.py    # 설정
├── data/
│   ├── documents/       # RAG 문서
│   └── chroma_db/       # 벡터 스토어
├── requirements.txt
└── README.md
```

### 새 에이전트 추가하기

1. **`app/graph/prompts.py`에 프롬프트 정의:**
```python
NEW_AGENT_PROMPT = """당신은 Ignition SCADA의 New Agent입니다.
책임:
- 특정 작업 1
- 특정 작업 2
"""
```

2. **`app/graph/nodes.py`에 에이전트 노드 생성:**
```python
def new_agent(state: GraphState):
    """특정 도메인 처리."""
    llm = ChatOllama(model=settings.llm_model_name, temperature=0)
    # ... 에이전트 로직 ...
    response.name = "New Agent"
    completed = state.get("agents_completed", 0) + 1
    return {"messages": [response], "agents_completed": completed}
```

3. **`app/graph/builder.py`에서 빌더 업데이트:**
```python
workflow.add_node("new_agent", new_agent)
workflow.add_edge("new_agent", "aggregate_results")
# _route_to_agents_parallel의 agent_node_map에 추가
```

4. **Supervisor 프롬프트 업데이트**하여 라우팅 로직에 새 에이전트 포함

## 🐛 문제 해결

### LLM이 응답하지 않음
```bash
# Ollama 서비스 확인
ollama list

# Ollama 재시작
systemctl restart ollama  # Linux
# 또는 Windows/Mac에서 Ollama 앱 재시작
```

### 데이터베이스 연결 실패
```bash
# MariaDB 확인
mysql -u user -p -e "SELECT 1"

# .env의 DATABASE_URL 확인
```

### 벡터 스토어가 비어있음
```bash
# 문서 확인
ls data/documents/

# Chroma 재초기화
python scripts/init_vectorstore.py
```

### 병렬 실행이 작동하지 않음
- 로그에서 "Dispatching to X (parallel)" 메시지 확인
- builder.py의 Send API import 확인
- agents_completed 카운터가 증가하는지 확인