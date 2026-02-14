# Human-in-the-Loop Migration Guide

## Overview

This guide explains the migration from the legacy approval workflow to the modern LangGraph 1.x interrupt-based HITL pattern.

## What Changed?

### Legacy Pattern (Phase 1)
- Separate `approval_storage.py` for in-memory pending actions
- Manual state management in `approve.py`
- Graph returns to client, client calls approval endpoint
- No automatic state persistence across restarts

### Modern Pattern (Phase 1.5 - LangGraph 1.x)
- **LangGraph `interrupt()`** - Built-in graph pausing
- **Command API** - Resume with human feedback
- **SQLite Checkpointer** - Automatic state persistence
- **Thread-based state** - Durable across server restarts

## Key Benefits

✅ **Simpler Code** - No manual pending action management
✅ **Persistent State** - Survives server restarts
✅ **Time Travel** - Can replay from any checkpoint
✅ **Production Ready** - Battle-tested by LangChain

## Architecture Comparison

### Legacy Flow
```
User Request → Graph → Tool Call →
  Create PendingAction → Store in memory →
  Return to client → Client calls /approve →
  Execute tool → Return result
```

### Modern Flow (LangGraph 1.x)
```
User Request → Graph → Tool Call →
  interrupt() → Save to checkpointer →
  Client gets interrupted state →
  Client calls /approve with Command →
  Graph resumes → Execute tool → Return result
```

## Implementation Details

### 1. State Persistence

**Before (Legacy):**
```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()  # Lost on restart
graph = workflow.compile(checkpointer=memory)
```

**After (Modern):**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("./data/checkpoints.db")
graph = workflow.compile(checkpointer=checkpointer)
```

### 2. Approval Workflow

**Before (Legacy):**
```python
# In tool node
if is_write_operation:
    action = PendingAction(...)
    store_pending_action(action)
    return {"pending_actions": [action]}

# In approve.py
def approve_action(request):
    action = get_pending_action(request.action_id)
    if request.approved:
        opc_client.write_tag(action.tag_path, action.value)
```

**After (Modern):**
```python
# In tool node
if is_write_operation:
    approval_request = {
        "action_id": uuid.uuid4(),
        "tag_path": tag_path,
        "value": value,
        ...
    }
    # This pauses the graph and saves state
    human_response = interrupt(approval_request)

    # When resumed, human_response contains the decision
    if human_response.get("approved"):
        # Execute write operation
        opc_client.write_tag(tag_path, value)

# In approve.py
def approve_action(request):
    # Resume the graph with Command
    result = graph.invoke(
        Command(resume={
            "approved": request.approved,
            "operator": request.operator,
            ...
        }),
        config={"configurable": {"thread_id": request.thread_id}}
    )
```

### 3. Thread Management

**Before:** No explicit thread management, used session-based storage

**After:** Thread-based state tracking
```python
config = {"configurable": {"thread_id": "user_session_123"}}

# Get current state
state = graph.get_state(config)

# Resume from specific checkpoint
state = graph.get_state(config, checkpoint_id="abc123")

# Invoke with thread context
result = graph.invoke(input, config=config)
```

## Migration Steps

### Step 1: Update Dependencies

```bash
# Update requirements.txt
pip install --upgrade langgraph langgraph-checkpoint langgraph-checkpoint-sqlite
```

### Step 2: Switch to Modern Builder

```python
# In main.py
from app.graph.builder import build_graph

# Use modern HITL (recommended)
app.state.app_graph = build_graph(
    use_modern_hitl=True,
    use_memory=False  # Use SQLite for production
)

# Or use legacy (backward compatibility)
app.state.app_graph = build_graph(
    use_modern_hitl=False,
    use_memory=True
)
```

### Step 3: Update API Routes

```python
# In router.py - Switch to new endpoints
from app.api.v1.ask_new import router as ask_router
from app.api.v1.approve_new import router as approve_router

# Or keep both for gradual migration
api_router.include_router(ask_router, tags=["Chat"])
api_router.include_router(approve_router, tags=["Approval"])
```

### Step 4: Update Client Code

**Before:**
```python
# 1. Send query
response = requests.post("/api/v1/ask", json={
    "question": "Turn off FAN1",
    "thread_id": "session_123"
})

# 2. Check for pending_action
if "pending_action" in response.json():
    action_id = response.json()["pending_action"]["id"]

    # 3. Approve
    requests.post("/api/v1/approve", json={
        "action_id": action_id,
        "approved": True,
        "operator": "John"
    })
```

**After (Modern):**
```python
# 1. Send query (same)
response = requests.post("/api/v1/ask", json={
    "question": "Turn off FAN1",
    "thread_id": "session_123"
})

# 2. Check status
data = response.json()
if data.get("status") == "pending_approval":
    # 3. Approve with thread_id
    requests.post("/api/v1/approve", json={
        "thread_id": "session_123",  # ← Key difference
        "action_id": data["pending_action"]["action_id"],
        "approved": True,
        "operator": "John"
    })
```

## Testing the Migration

### Test 1: Basic Approval Flow

```bash
# Start server
uvicorn app.main:app --reload

# Terminal 1: Send write request
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "FAN1을 꺼줘",
    "thread_id": "test_thread_001"
  }'

# Response should include pending_action with action_id

# Terminal 2: Check thread state
curl http://localhost:8000/api/v1/state/test_thread_001

# Terminal 3: Approve
curl -X POST http://localhost:8000/api/v1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test_thread_001",
    "action_id": "abc-123-...",
    "approved": true,
    "operator": "TestUser"
  }'
```

### Test 2: State Persistence

```bash
# 1. Send request that gets interrupted
curl -X POST http://localhost:8000/api/v1/ask \
  -d '{"question": "Turn off FAN1", "thread_id": "persist_test"}'

# 2. Restart server
# Kill and restart uvicorn

# 3. Check state still exists
curl http://localhost:8000/api/v1/state/persist_test

# 4. Approve (should still work!)
curl -X POST http://localhost:8000/api/v1/approve \
  -d '{"thread_id": "persist_test", ...}'
```

### Test 3: Rejection Flow

```bash
curl -X POST http://localhost:8000/api/v1/approve \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test_thread_001",
    "action_id": "abc-123-...",
    "approved": false,
    "operator": "TestUser",
    "notes": "Not authorized during maintenance"
  }'
```

## Rollback Plan

If issues occur, you can rollback by:

1. **Set `use_modern_hitl=False` in main.py**
```python
app.state.app_graph = build_graph(use_modern_hitl=False)
```

2. **Use legacy endpoints**
```python
# In router.py
from app.api.v1.ask import router as ask_router  # Legacy
from app.api.v1.approve import router as approve_router  # Legacy
```

3. **Both patterns can coexist** - Gradual migration is supported

## Troubleshooting

### Issue: "Thread not found"
**Solution:** Ensure thread_id is consistent between /ask and /approve calls

### Issue: "Graph not interrupted"
**Solution:** Check that `use_modern_hitl=True` in build_graph()

### Issue: Checkpoints.db is large
**Solution:** Implement checkpoint pruning:
```python
# Prune old checkpoints (>30 days)
checkpointer.delete_old_checkpoints(days=30)
```

### Issue: State persistence not working
**Solution:** Verify SQLite file permissions and path exists

## Advanced Features

### Time Travel Debugging

```python
# List all checkpoints for a thread
checkpoints = list(checkpointer.list(config))

# Replay from specific checkpoint
state = graph.get_state(config, checkpoint_id="abc123")
```

### Custom Interrupt Policies

```python
# Interrupt only for high-risk operations
if risk_level == "high":
    human_response = interrupt(approval_request)
elif risk_level == "medium":
    # Auto-approve with logging
    log_operation(tag_path, value)
    execute_write()
else:
    # Auto-execute low-risk
    execute_write()
```

## Further Reading

- [LangGraph Interrupts Documentation](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Persistence Guide](https://fast.io/resources/langgraph-persistence/)
- [Human-in-the-Loop Tutorial (IBM)](https://www.ibm.com/think/tutorials/human-in-the-loop-ai-agent-langraph-watsonx-ai)
- [Making it easier to build HITL agents](https://blog.langchain.com/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt/)

## Sources

This migration guide is based on:
- [Interrupts - Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [How to wait for user input using interrupt](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/wait-user-input/)
- [Human-in-the-Loop Agent Using Interrupt and Command in LangGraph](https://medium.com/fundamentals-of-artificial-intelligence/human-in-the-loop-agent-using-interrupt-and-command-in-langgraph-f3895051aeb8)
- [Architecting Human-in-the-Loop Agents](https://medium.com/data-science-collective/architecting-human-in-the-loop-agents-interrupts-persistence-and-state-management-in-langgraph-fa36c9663d6f)
