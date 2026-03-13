"""Main workflow orchestrator - coordinates all 4 agents"""
import logging
import time
import uuid
from typing import Dict, Any
from datetime import datetime

from agents.agent_1_document_analyzer import DocumentAnalyzerAgent
from agents.agent_2_rules_validator import RulesValidatorAgent
from agents.agent_3_field_mapper import FieldMapperAgent
from agents.agent_4_pdf_generator import PDFGeneratorAgent
from agents.base import AgentInput, AgentOutput
from models.schemas import WorkflowOutput

logger = logging.getLogger(__name__)


class FormAutomationWorkflow:
    """
    Orchestrates the complete form automation pipeline:
    1. Document Analyzer (Agent 1) - Extract identity from document
    2. Rules Validator (Agent 2) - Validate eligibility
    3. Field Mapper (Agent 3) - Map fields to form
    4. PDF Generator (Agent 4) - Create filled PDF
    """
    
    def __init__(self, gemini_api_key: str):
        self.gemini_api_key = gemini_api_key
        self.agent_1 = DocumentAnalyzerAgent(gemini_api_key)
        self.agent_2 = RulesValidatorAgent(gemini_api_key)
        self.agent_3 = FieldMapperAgent(gemini_api_key)
        self.agent_4 = PDFGeneratorAgent()
        self.workflow_id = None
        self.start_time = None
    
    async def execute(self, workflow_input: Dict[str, Any]) -> WorkflowOutput:
        """
        Execute the complete workflow:
        
        Args:
            workflow_input: Dictionary containing:
                - document_image: Base64 encoded image of identity document
                - document_type: "aadhaar", "passport", etc.
                - form_fields: List of target form field definitions
                - country: Country code for eligibility check
                - app_type: Application type for rules validation
                - form_title: Title of the form being filled
        
        Returns:
            WorkflowOutput: Complete workflow result with all agent outputs
        """
        
        self.workflow_id = str(uuid.uuid4())
        self.start_time = time.time()
        
        logger.info(f"Starting workflow {self.workflow_id}")
        
        workflow_output = WorkflowOutput(
            workflow_id=self.workflow_id,
            status="in_progress"
        )
        
        try:
            # ===== Agent 1: Document Analysis =====
            logger.info(f"[{self.workflow_id}] Running Agent 1: Document Analyzer")
            
            agent_1_input = AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "document_image": workflow_input.get("document_image"),
                    "document_type": workflow_input.get("document_type", "generic")
                }
            )
            
            agent_1_result = await self.agent_1.run(agent_1_input)
            
            if agent_1_result.status == "error":
                logger.error(f"[{self.workflow_id}] Agent 1 failed: {agent_1_result.errors}")
                workflow_output.status = "failed"
                workflow_output.errors = agent_1_result.errors
                workflow_output.message = "Document analysis failed"
                return workflow_output
            
            profile = agent_1_result.data.get("profile", agent_1_result.data)
            logger.info(f"[{self.workflow_id}] Agent 1 complete: confidence {agent_1_result.confidence:.2%}")
            
            # ===== Agent 2: Rules Validation =====
            logger.info(f"[{self.workflow_id}] Running Agent 2: Rules Validator")
            
            agent_2_input = AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "profile": profile,
                    "country": workflow_input.get("country", "IN"),
                    "app_type": workflow_input.get("app_type", "visa")
                }
            )
            
            agent_2_result = await self.agent_2.run(agent_2_input)
            
            if agent_2_result.status == "error":
                logger.warning(f"[{self.workflow_id}] Agent 2 warning: {agent_2_result.errors}")
                # Don't fail the workflow - validation is informational
            else:
                logger.info(f"[{self.workflow_id}] Agent 2 complete: {agent_2_result.data}")
            
            validation = agent_2_result.data
            
            # ===== Agent 3: Field Mapping =====
            logger.info(f"[{self.workflow_id}] Running Agent 3: Field Mapper")
            
            agent_3_input = AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "profile": profile,
                    "form_fields": workflow_input.get("form_fields", [])
                }
            )
            
            agent_3_result = await self.agent_3.run(agent_3_input)
            
            if agent_3_result.status == "error":
                logger.error(f"[{self.workflow_id}] Agent 3 failed: {agent_3_result.errors}")
                workflow_output.status = "failed"
                workflow_output.errors = agent_3_result.errors
                workflow_output.message = "Field mapping failed"
                return workflow_output
            
            mappings = agent_3_result.data.get("mappings", [])
            logger.info(f"[{self.workflow_id}] Agent 3 complete: mapped {len(mappings)} fields")
            
            # ===== Agent 4: PDF Generation =====
            logger.info(f"[{self.workflow_id}] Running Agent 4: PDF Generator")
            
            agent_4_input = AgentInput(
                workflow_id=self.workflow_id,
                metadata={
                    "mappings": mappings,
                    "profile": profile,
                    "form_title": workflow_input.get("form_title", "Filled Form")
                }
            )
            
            agent_4_result = await self.agent_4.run(agent_4_input)
            
            if agent_4_result.status == "error":
                logger.error(f"[{self.workflow_id}] Agent 4 failed: {agent_4_result.errors}")
                workflow_output.status = "failed"
                workflow_output.errors = agent_4_result.errors
                workflow_output.message = "PDF generation failed"
                return workflow_output
            
            pdf_base64 = agent_4_result.data.get("pdf_base64")
            file_name = agent_4_result.data.get("file_name")
            logger.info(f"[{self.workflow_id}] Agent 4 complete: PDF generated")
            
            # ===== Workflow Complete =====
            elapsed_ms = int((time.time() - self.start_time) * 1000)
            
            workflow_output.status = "completed"
            workflow_output.profile = profile
            workflow_output.validation = validation
            workflow_output.mappings = mappings
            workflow_output.pdf_base64 = pdf_base64
            workflow_output.pdf_file_name = file_name
            workflow_output.completed_at = datetime.now()
            workflow_output.message = f"Workflow completed in {elapsed_ms}ms"
            
            logger.info(
                f"[{self.workflow_id}] Workflow complete in {elapsed_ms}ms. "
                f"Confidence: Document={agent_1_result.confidence:.2%}, "
                f"Mapping={agent_3_result.confidence:.2%}"
            )
            
            return workflow_output
        
        except Exception as e:
            logger.error(f"[{self.workflow_id}] Workflow error: {str(e)}", exc_info=True)
            workflow_output.status = "failed"
            workflow_output.errors = [str(e)]
            workflow_output.message = f"Unexpected error: {str(e)}"
            return workflow_output
    
    def get_default_form_fields(self) -> list:
        """Return default form field definitions"""
        return [
            {"name": "fullName", "label": "Full Name", "required": True},
            {"name": "firstName", "label": "First Name", "required": True},
            {"name": "lastName", "label": "Last Name", "required": True},
            {"name": "dateOfBirth", "label": "Date of Birth", "required": True},
            {"name": "gender", "label": "Gender", "required": True},
            {"name": "address", "label": "Street Address", "required": True},
            {"name": "city", "label": "City", "required": True},
            {"name": "state", "label": "State/Province", "required": True},
            {"name": "pincode", "label": "Postal Code", "required": True},
            {"name": "documentId", "label": "Document ID", "required": True},
            {"name": "documentType", "label": "Document Type", "required": True},
        ]
