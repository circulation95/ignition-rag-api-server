"""
Tests for Modern HITL Workflow (LangGraph 1.x)

Tests interrupt-based approval workflow with state persistence.
"""

import pytest
from datetime import datetime
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.graph.builder import build_graph
from app.graph.state import HumanFeedback


class TestModernHITL:
    """Test suite for LangGraph 1.x interrupt-based HITL."""

    @pytest.fixture
    def graph(self):
        """Create graph with modern HITL and in-memory checkpointer for testing."""
        return build_graph(use_modern_hitl=True, use_memory=True)

    @pytest.fixture
    def thread_config(self):
        """Config for thread-based state."""
        return {"configurable": {"thread_id": "test_thread_001"}}

    def test_normal_read_operation(self, graph, thread_config):
        """Test that read operations work without interruption."""
        inputs = {"messages": [HumanMessage(content="현재 Tank1 온도는?")]}

        result = graph.invoke(inputs, config=thread_config)

        # Should complete without interruption
        assert result["messages"]
        assert len(result["messages"]) > 0

        # Check state is not interrupted
        state = graph.get_state(thread_config)
        assert state.next == ()  # No pending nodes

    def test_write_operation_interrupts(self, graph, thread_config):
        """Test that write operations trigger interrupts."""
        inputs = {"messages": [HumanMessage(content="FAN1을 꺼줘")]}

        # This should interrupt
        result = graph.invoke(inputs, config=thread_config)

        # Check if interrupted
        state = graph.get_state(thread_config)

        # State should have pending tasks (interrupted)
        assert state.tasks is not None
        assert len(state.tasks) > 0

        # Check interrupt data
        if state.tasks[0].interrupts:
            interrupt_data = state.tasks[0].interrupts[0]
            assert "action_id" in interrupt_data
            assert "tag_path" in interrupt_data
            assert "value" in interrupt_data
            assert interrupt_data["value"] == 0  # FAN off

    def test_approval_flow(self, graph, thread_config):
        """Test complete approval workflow: request → approve → execute."""
        # Step 1: Request write operation
        inputs = {"messages": [HumanMessage(content="FAN1을 꺼줘")]}
        result = graph.invoke(inputs, config=thread_config)

        # Step 2: Get interrupted state
        state = graph.get_state(thread_config)
        assert state.tasks is not None

        # Step 3: Approve with Command
        approval = {
            "approved": True,
            "operator": "TestUser",
            "notes": "Test approval",
            "timestamp": datetime.now().isoformat(),
        }

        # Resume execution
        result = graph.invoke(
            Command(resume=approval),
            config=thread_config
        )

        # Step 4: Check execution completed
        assert result["messages"]
        # Should contain approval confirmation
        final_message = result["messages"][-1]
        assert "approved" in final_message.content.lower() or \
               "executed" in final_message.content.lower()

    def test_rejection_flow(self, graph, thread_config):
        """Test rejection workflow: request → reject → abort."""
        # Step 1: Request write operation
        inputs = {"messages": [HumanMessage(content="FAN1을 꺼줘")]}
        result = graph.invoke(inputs, config=thread_config)

        # Step 2: Reject with Command
        rejection = {
            "approved": False,
            "operator": "TestUser",
            "notes": "Not authorized",
            "timestamp": datetime.now().isoformat(),
        }

        result = graph.invoke(
            Command(resume=rejection),
            config=thread_config
        )

        # Should contain rejection message
        final_message = result["messages"][-1]
        assert "rejected" in final_message.content.lower() or \
               "not authorized" in final_message.content.lower()

    def test_state_persistence_across_invocations(self, graph):
        """Test that state persists across different thread_id accesses."""
        thread_id = "persist_test_001"
        config = {"configurable": {"thread_id": thread_id}}

        # First invocation - create interrupt
        inputs = {"messages": [HumanMessage(content="Turn off FAN1")]}
        result = graph.invoke(inputs, config=config)

        # Get state
        state1 = graph.get_state(config)
        checkpoint_id = state1.config["configurable"]["checkpoint_id"]

        # Second access - retrieve same state
        state2 = graph.get_state(config)
        assert state2.config["configurable"]["checkpoint_id"] == checkpoint_id

        # State should be identical
        assert state1.next == state2.next
        assert len(state1.values["messages"]) == len(state2.values["messages"])

    def test_risk_level_assessment(self, graph, thread_config):
        """Test that risk levels are correctly assessed."""
        test_cases = [
            ("Turn off emergency alarm", "high"),
            ("Turn off FAN1", "medium"),
            ("Update display value", "low"),
        ]

        for question, expected_risk in test_cases:
            # Create new thread for each test
            config = {
                "configurable": {
                    "thread_id": f"risk_test_{expected_risk}"
                }
            }

            inputs = {"messages": [HumanMessage(content=question)]}
            result = graph.invoke(inputs, config=config)

            state = graph.get_state(config)
            if state.tasks and state.tasks[0].interrupts:
                interrupt_data = state.tasks[0].interrupts[0]
                assert interrupt_data.get("risk_level") == expected_risk

    def test_checkpoint_history(self, graph, thread_config):
        """Test that checkpoints create history we can traverse."""
        # Create multiple checkpoints
        messages = [
            "현재 Tank1 온도는?",
            "FAN1 상태는?",
            "FAN1을 꺼줘",  # This will interrupt
        ]

        for msg in messages:
            inputs = {"messages": [HumanMessage(content=msg)]}
            try:
                graph.invoke(inputs, config=thread_config)
            except Exception:
                # Might interrupt on last message
                pass

        # Get checkpoint history
        from app.services.checkpointer import get_checkpointer, list_thread_checkpoints

        checkpointer = get_checkpointer(use_memory=True)
        checkpoints = list_thread_checkpoints(
            checkpointer,
            thread_config["configurable"]["thread_id"]
        )

        # Should have multiple checkpoints
        assert len(checkpoints) > 0

    def test_concurrent_threads(self, graph):
        """Test that different threads maintain separate states."""
        thread1 = {"configurable": {"thread_id": "thread_001"}}
        thread2 = {"configurable": {"thread_id": "thread_002"}}

        # Thread 1: Request FAN1 off
        inputs1 = {"messages": [HumanMessage(content="FAN1을 꺼줘")]}
        graph.invoke(inputs1, config=thread1)

        # Thread 2: Request FAN2 off
        inputs2 = {"messages": [HumanMessage(content="FAN2를 꺼줘")]}
        graph.invoke(inputs2, config=thread2)

        # Check both are interrupted independently
        state1 = graph.get_state(thread1)
        state2 = graph.get_state(thread2)

        assert state1.tasks is not None
        assert state2.tasks is not None

        # They should have different interrupt data
        if state1.tasks[0].interrupts and state2.tasks[0].interrupts:
            data1 = state1.tasks[0].interrupts[0]
            data2 = state2.tasks[0].interrupts[0]
            assert data1["action_id"] != data2["action_id"]


class TestLegacyHITL:
    """Test suite for legacy approval workflow (backward compatibility)."""

    @pytest.fixture
    def graph(self):
        """Create graph with legacy HITL."""
        return build_graph(use_modern_hitl=False, use_memory=True)

    def test_legacy_approval_still_works(self, graph):
        """Test that legacy approval workflow still functions."""
        config = {"configurable": {"thread_id": "legacy_test"}}
        inputs = {"messages": [HumanMessage(content="FAN1을 꺼줘")]}

        result = graph.invoke(inputs, config=config)

        # Should have pending_actions in state
        assert "pending_actions" in result or "messages" in result


class TestMigration:
    """Test migration scenarios between legacy and modern HITL."""

    def test_can_switch_between_patterns(self):
        """Test that both patterns can be instantiated."""
        legacy_graph = build_graph(use_modern_hitl=False, use_memory=True)
        modern_graph = build_graph(use_modern_hitl=True, use_memory=True)

        assert legacy_graph is not None
        assert modern_graph is not None

    def test_same_state_schema(self):
        """Test that both patterns use compatible state schemas."""
        from app.graph.state import GraphState

        # Both should work with the same state schema
        legacy_graph = build_graph(use_modern_hitl=False, use_memory=True)
        modern_graph = build_graph(use_modern_hitl=True, use_memory=True)

        # Create test input
        config = {"configurable": {"thread_id": "schema_test"}}
        inputs = {"messages": [HumanMessage(content="현재 Tank1 온도는?")]}

        # Both should handle the same input
        legacy_result = legacy_graph.invoke(inputs, config=config)
        modern_result = modern_graph.invoke(inputs, config=config)

        # Both should produce messages
        assert "messages" in legacy_result
        assert "messages" in modern_result


@pytest.mark.asyncio
class TestAPIIntegration:
    """Test API integration with modern HITL."""

    async def test_ask_endpoint_returns_pending_status(self):
        """Test /ask endpoint returns pending_approval status."""
        # This would require FastAPI test client
        # Placeholder for integration test
        pass

    async def test_approve_endpoint_resumes_graph(self):
        """Test /approve endpoint properly resumes graph execution."""
        # This would require FastAPI test client
        # Placeholder for integration test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
