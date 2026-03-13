"""Base classes for all agents"""
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class AgentInput(BaseModel):
    """Base contract for all agent inputs"""
    workflow_id: str = ""
    timestamp: datetime = None
    metadata: Dict[str, Any] = {}
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.workflow_id:
            self.workflow_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now()


class AgentOutput(BaseModel):
    """Base contract for all agent outputs"""
    status: str  # "success" | "error" | "warning"
    data: Dict[str, Any] = {}
    confidence: float = 0.0  # 0.0-1.0
    execution_time_ms: int = 0
    errors: List[str] = []
    warnings: List[str] = []


class Agent(ABC):
    """Base class for all agents - enforce consistent interface"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Agent.{name}")
    
    @abstractmethod
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Execute agent logic - override in subclass"""
        pass
    
    async def run(self, input_data: AgentInput) -> AgentOutput:
        """Execute with error handling, logging, and timing"""
        start_time = time.time()
        
        self.logger.info(
            f"Starting {self.name} for workflow {input_data.workflow_id}"
        )
        
        try:
            result = await self.execute(input_data)
            result.execution_time_ms = int((time.time() - start_time) * 1000)
            
            self.logger.info(
                f"{self.name} completed in {result.execution_time_ms}ms | "
                f"Status: {result.status} | Confidence: {result.confidence:.2f}"
            )
            
            return result
        
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            self.logger.error(
                f"{self.name} failed: {str(e)}",
                exc_info=True
            )
            return AgentOutput(
                status="error",
                data={},
                confidence=0,
                execution_time_ms=execution_time,
                errors=[str(e)]
            )
