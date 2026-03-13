"""FastAPI application - Main entry point for FormPilot backend"""
import os
import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from workflows.form_automation_workflow import FormAutomationWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set. Set it in .env file")

# Create FastAPI app
app = FastAPI(
    title="FormPilot Enterprise API",
    description="Multi-agent form automation system",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize workflow
workflow = FormAutomationWorkflow(GEMINI_API_KEY) if GEMINI_API_KEY else None

# Store workflow state (in-memory for now, would use database in production)
workflow_states: Dict[str, Any] = {}


# ===== Request/Response Models =====
class WorkflowStartRequest(BaseModel):
    """Request to start a new workflow"""
    document_image: str  # Base64 encoded image
    document_type: str = "passport"  # "aadhaar", "passport", etc.
    form_fields: list = []  # Form field definitions
    country: str = "IN"  # Country code
    app_type: str = "visa"  # Application type
    form_title: str = "Government Form"


class WorkflowStatusResponse(BaseModel):
    """Response with workflow status"""
    workflow_id: str
    status: str
    progress: int = 0
    message: str = ""


class WorkflowResultResponse(BaseModel):
    """Response with complete workflow result"""
    workflow_id: str
    status: str
    profile: Dict = {}
    validation: Dict = {}
    mappings: list = []
    pdf_base64: str = ""
    pdf_file_name: str = ""
    message: str = ""


# ===== Health Check =====
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FormPilot Enterprise API",
        "version": "1.0.0",
        "gemini_configured": GEMINI_API_KEY is not None
    }


# ===== Workflow Endpoints =====
@app.post("/api/workflows/start", tags=["Workflows"])
async def start_workflow(request: WorkflowStartRequest):
    """
    Start a new form automation workflow
    
    Args:
        request: WorkflowStartRequest with document image and configuration
    
    Returns:
        Workflow ID and initial status
    """
    
    if not workflow:
        raise HTTPException(status_code=503, detail="Gemini API not configured")
    
    try:
        logger.info(f"Starting new workflow with document type: {request.document_type}")
        
        # Execute workflow
        workflow_result = await workflow.execute({
            "document_image": request.document_image,
            "document_type": request.document_type,
            "form_fields": request.form_fields or workflow.get_default_form_fields(),
            "country": request.country,
            "app_type": request.app_type,
            "form_title": request.form_title
        })
        
        # Store result
        workflow_states[workflow_result.workflow_id] = workflow_result
        
        return {
            "workflow_id": workflow_result.workflow_id,
            "status": workflow_result.status,
            "message": workflow_result.message,
            "profile": workflow_result.profile,
            "validation": workflow_result.validation,
            "mappings": workflow_result.mappings,
            "pdf_file_name": workflow_result.pdf_file_name,
            "pdf_base64": workflow_result.pdf_base64 if workflow_result.status == "completed" else None
        }
    
    except Exception as e:
        logger.error(f"Workflow error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")


@app.get("/api/workflows/{workflow_id}/status", tags=["Workflows"])
async def get_workflow_status(workflow_id: str):
    """
    Get the status of a running workflow
    
    Args:
        workflow_id: The workflow ID
    
    Returns:
        Current workflow status and progress
    """
    
    result = workflow_states.get(workflow_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    return {
        "workflow_id": workflow_id,
        "status": result.status,
        "message": result.message
    }


@app.get("/api/workflows/{workflow_id}/result", tags=["Workflows"])
async def get_workflow_result(workflow_id: str):
    """
    Get the complete result of a finished workflow
    
    Args:
        workflow_id: The workflow ID
    
    Returns:
        Complete workflow output including PDF
    """
    
    result = workflow_states.get(workflow_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if result.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Workflow status is {result.status}, result not available"
        )
    
    return {
        "workflow_id": workflow_id,
        "status": result.status,
        "message": result.message,
        "profile": result.profile,
        "validation": result.validation,
        "mappings": result.mappings,
        "pdf_file_name": result.pdf_file_name,
        "pdf_base64": result.pdf_base64
    }


@app.post("/api/workflows/{workflow_id}/cancel", tags=["Workflows"])
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow"""
    
    result = workflow_states.get(workflow_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    if result.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel workflow in {result.status} state"
        )
    
    result.status = "cancelled"
    
    return {
        "workflow_id": workflow_id,
        "status": "cancelled",
        "message": "Workflow cancelled"
    }


@app.delete("/api/workflows/{workflow_id}", tags=["Workflows"])
async def delete_workflow(workflow_id: str):
    """Delete workflow history"""
    
    if workflow_id not in workflow_states:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    del workflow_states[workflow_id]
    
    return {
        "message": f"Workflow {workflow_id} deleted"
    }


# ===== Info Endpoints =====
@app.get("/api/form-fields", tags=["Configuration"])
async def get_default_form_fields():
    """Get default form field definitions"""
    
    return {
        "form_fields": workflow.get_default_form_fields() if workflow else []
    }


@app.get("/api/supported-documents", tags=["Configuration"])
async def get_supported_documents():
    """Get list of supported document types"""
    
    return {
        "document_types": [
            {"type": "passport", "description": "International Passport"},
            {"type": "aadhaar", "description": "Aadhaar (Indian ID)"},
            {"type": "driving_license", "description": "Driving License"},
            {"type": "visa", "description": "Visa Document"},
            {"type": "generic", "description": "Generic Identity Document"}
        ]
    }


@app.get("/api/supported-countries", tags=["Configuration"])
async def get_supported_countries():
    """Get list of supported countries for eligibility check"""
    
    return {
        "countries": [
            {"code": "IN", "name": "India"},
            {"code": "US", "name": "United States"},
            {"code": "UK", "name": "United Kingdom"},
            {"code": "CA", "name": "Canada"}
        ]
    }


# ===== Error Handlers =====
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle uncaught exceptions"""
    logger.error(f"Uncaught exception: {str(exc)}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ===== Summary Endpoint =====
@app.get("/", tags=["System"])
async def root():
    """API documentation"""
    return {
        "name": "FormPilot Enterprise API",
        "version": "1.0.0",
        "description": "Multi-agent form automation system for government applications",
        "endpoints": {
            "health": "GET /health",
            "start_workflow": "POST /api/workflows/start",
            "workflow_status": "GET /api/workflows/{workflow_id}/status",
            "workflow_result": "GET /api/workflows/{workflow_id}/result",
            "cancel_workflow": "POST /api/workflows/{workflow_id}/cancel",
            "delete_workflow": "DELETE /api/workflows/{workflow_id}",
            "form_fields": "GET /api/form-fields",
            "supported_documents": "GET /api/supported-documents",
            "supported_countries": "GET /api/supported-countries"
        }
    }


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    
    logger.info(f"Starting FormPilot API on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
