"""Tests for Agent base classes"""
import pytest
import asyncio
from agents.base import Agent, AgentInput, AgentOutput


class SimpleTestAgent(Agent):
    """Simple test agent for testing base class"""
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Simple test implementation"""
        value = input_data.metadata.get("value", 0)
        
        if value < 0:
            raise ValueError("Value must be positive")
        
        return AgentOutput(
            status="success",
            data={"result": value * 2},
            confidence=0.95
        )


@pytest.mark.asyncio
async def test_agent_input_creation():
    """Test AgentInput creation"""
    input_data = AgentInput(
        workflow_id="test-123",
        metadata={"test": "value"}
    )
    
    assert input_data.workflow_id == "test-123"
    assert input_data.metadata["test"] == "value"
    assert input_data.timestamp is not None


@pytest.mark.asyncio
async def test_agent_output_creation():
    """Test AgentOutput creation"""
    output = AgentOutput(
        status="success",
        data={"result": 42},
        confidence=0.95
    )
    
    assert output.status == "success"
    assert output.data["result"] == 42
    assert output.confidence == 0.95
    assert output.execution_time_ms >= 0


@pytest.mark.asyncio
async def test_agent_run_success():
    """Test agent successful execution"""
    agent = SimpleTestAgent(name="TestAgent")
    
    input_data = AgentInput(
        workflow_id="test-123",
        metadata={"value": 10}
    )
    
    result = await agent.run(input_data)
    
    assert result.status == "success"
    assert result.data["result"] == 20
    assert result.confidence == 0.95
    assert result.execution_time_ms >= 0


@pytest.mark.asyncio
async def test_agent_run_error_handling():
    """Test agent error handling"""
    agent = SimpleTestAgent(name="TestAgent")
    
    input_data = AgentInput(
        workflow_id="test-123",
        metadata={"value": -5}
    )
    
    result = await agent.run(input_data)
    
    assert result.status == "error"
    assert len(result.errors) > 0
    assert "Value must be positive" in result.errors[0]


@pytest.mark.asyncio
async def test_agent_timing():
    """Test agent execution timing"""
    agent = SimpleTestAgent(name="TestAgent")
    
    input_data = AgentInput(
        workflow_id="test-123",
        metadata={"value": 10}
    )
    
    result = await agent.run(input_data)
    
    # Execution should be very fast (< 100ms)
    assert result.execution_time_ms < 100
    assert result.execution_time_ms >= 0
