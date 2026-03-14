"""FastAPI application - Main entry point for FormPilot backend"""
import os
import logging
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
    description="AI-powered multi-agent form automation — Airia Hackathon 2026",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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


# ===== Frontend Route =====
@app.get("/", response_class=HTMLResponse, tags=["Frontend"], include_in_schema=False)
async def serve_frontend():
    """Serve the FormPilot frontend application"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return HTMLResponse("""
    <html><body style="font-family:sans-serif;padding:40px;background:#0a0e1a;color:#f1f5f9">
    <h1>🚀 FormPilot API is running!</h1>
    <p>Visit <a href="/docs" style="color:#4f8ef7">/docs</a> for the API documentation.</p>
    </body></html>
    """)


# ===== Demo Endpoint =====
@app.post("/api/workflows/demo", tags=["Workflows"])
async def demo_workflow():
    """
    Run a demo workflow with mock data — no API key required.
    Perfect for judges to test without uploading real documents.
    """
    import uuid
    import base64
    import io
    from datetime import datetime
    from agents.agent_4_pdf_generator import PDFGeneratorAgent
    from agents.base import AgentInput

    demo_profile = {
        "fullName": {"value": "PRANJAL KUMAR SINGH", "confidence": 0.97, "source": "gemini"},
        "dob": {"value": "15/05/1998", "confidence": 0.95, "source": "gemini"},
        "gender": {"value": "Male", "confidence": 0.99, "source": "gemini"},
        "address": {
            "street": {"value": "123, MG Road, Sector 5", "confidence": 0.91, "source": "gemini"},
            "city": {"value": "Bangalore", "confidence": 0.94, "source": "gemini"},
            "state": {"value": "Karnataka", "confidence": 0.93, "source": "gemini"},
            "pincode": {"value": "560001", "confidence": 0.96, "source": "gemini"},
        },
        "documentId": {"value": "1234 5678 9012", "confidence": 0.98, "source": "gemini"},
        "documentType": "aadhaar",
        "overallConfidence": 0.95,
        "warnings": [],
        "extracted_at": datetime.now().isoformat()
    }

    demo_validation = {
        "eligible": True,
        "validationResults": [
            {"check": "Age Requirement", "passed": True, "requirement": "18+ years", "explanation": "Age 27 — meets 18+ requirement"},
            {"check": "Valid Identity Document", "passed": True, "requirement": "Aadhaar / Passport / PAN", "explanation": "Aadhaar detected with confidence 95%"},
            {"check": "Residency Status", "passed": True, "requirement": "Indian resident", "explanation": "Address shows Karnataka, India"},
            {"check": "Data Completeness", "passed": True, "requirement": "All required fields", "explanation": "Name, DOB, address, document ID all present"},
        ],
        "missingFields": [],
        "notes": "Applicant meets all eligibility requirements for Passport Application.",
        "country": "IN",
        "app_type": "passport",
        "validated_at": datetime.now().isoformat()
    }

    demo_mappings = [
        {"formField": "fullName", "profileField": "fullName", "value": "PRANJAL KUMAR SINGH", "transformation": "none", "confidence": 0.97},
        {"formField": "firstName", "profileField": "fullName", "value": "PRANJAL KUMAR", "transformation": "split", "confidence": 0.95},
        {"formField": "lastName", "profileField": "fullName", "value": "SINGH", "transformation": "split", "confidence": 0.95},
        {"formField": "dateOfBirth", "profileField": "dob", "value": "15/05/1998", "transformation": "none", "confidence": 0.95},
        {"formField": "gender", "profileField": "gender", "value": "Male", "transformation": "none", "confidence": 0.99},
        {"formField": "address", "profileField": "address.street", "value": "123, MG Road, Sector 5", "transformation": "none", "confidence": 0.91},
        {"formField": "city", "profileField": "address.city", "value": "Bangalore", "transformation": "none", "confidence": 0.94},
        {"formField": "state", "profileField": "address.state", "value": "Karnataka", "transformation": "none", "confidence": 0.93},
        {"formField": "pincode", "profileField": "address.pincode", "value": "560001", "transformation": "none", "confidence": 0.96},
        {"formField": "documentId", "profileField": "documentId", "value": "1234 5678 9012", "transformation": "none", "confidence": 0.98},
        {"formField": "documentType", "profileField": "documentType", "value": "Aadhaar Card", "transformation": "none", "confidence": 1.0},
    ]

    # Generate real PDF
    agent_4 = PDFGeneratorAgent()
    pdf_input = AgentInput(
        workflow_id=str(uuid.uuid4()),
        metadata={
            "mappings": demo_mappings,
            "profile": demo_profile,
            "form_title": "Passport Application Form - Demo"
        }
    )
    pdf_result = await agent_4.run(pdf_input)

    wf_id = str(uuid.uuid4())
    return {
        "workflow_id": wf_id,
        "status": "completed",
        "message": "Demo workflow completed successfully",
        "profile": demo_profile,
        "validation": demo_validation,
        "mappings": demo_mappings,
        "pdf_file_name": pdf_result.data.get("file_name", "demo_form.pdf"),
        "pdf_base64": pdf_result.data.get("pdf_base64", ""),
        "demo": True
    }


# ===== Summary Endpoint =====
@app.get("/api", tags=["System"])
async def api_info():
    """API information"""
    return {
        "name": "FormPilot Enterprise API",
        "version": "1.0.0",
        "description": "Multi-agent form automation system for government applications",
        "gemini_configured": GEMINI_API_KEY is not None,
        "endpoints": {
            "health": "GET /health",
            "frontend": "GET /",
            "demo": "POST /api/workflows/demo",
            "start_workflow": "POST /api/workflows/start",
            "workflow_status": "GET /api/workflows/{workflow_id}/status",
            "workflow_result": "GET /api/workflows/{workflow_id}/result",
            "form_fields": "GET /api/form-fields",
            "supported_documents": "GET /api/supported-documents",
            "supported_countries": "GET /api/supported-countries",
            "api_docs": "GET /docs"
        }
    }


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))

    logger.info(f"Starting FormPilot API on {host}:{port}")
    logger.info(f"Frontend: http://{host}:{port}/")
    logger.info(f"API Docs: http://{host}:{port}/docs")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
