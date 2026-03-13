#!/usr/bin/env python3
"""
Quick Start Script - Test FormPilot locally
Run this script to test the complete workflow without a frontend
"""

import asyncio
import base64
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

async def main():
    """Run a quick test of the complete workflow"""
    
    # Import after adding to path
    from workflows.form_automation_workflow import FormAutomationWorkflow
    
    # Get API key from environment
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not set")
        print("Please set GEMINI_API_KEY in .env file")
        return
    
    print("🚀 FormPilot Quick Start Test")
    print("=" * 50)
    
    # Create workflow
    workflow = FormAutomationWorkflow(api_key)
    
    # Sample image (1x1 pixel PNG)
    manual_image_path = Path(__file__).parent / "tests" / "manual_assets" / "simulated_passport.png"
    if manual_image_path.exists():
        sample_image_bytes = manual_image_path.read_bytes()
    else:
        sample_image_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
    sample_image_base64 = base64.b64encode(sample_image_bytes).decode('utf-8')
    
    # Create workflow input
    workflow_input = {
        "document_image": sample_image_base64,
        "document_type": "passport",
        "form_fields": [
            {"name": "fullName"},
            {"name": "dateOfBirth"},
            {"name": "gender"},
        ],
        "country": "IN",
        "app_type": "visa",
        "form_title": "Sample Visa Application"
    }
    
    print("\n📋 Starting workflow...")
    print(f"   Document Type: {workflow_input['document_type']}")
    print(f"   Form Fields: {len(workflow_input['form_fields'])} fields")
    print(f"   Country: {workflow_input['country']}")
    
    # Execute workflow
    try:
        result = await workflow.execute(workflow_input)
        
        print(f"\n✅ Workflow Complete!")
        print(f"   Status: {result.status}")
        print(f"   Workflow ID: {result.workflow_id}")
        
        if result.status == "completed":
            print(f"\n📊 Results:")
            print(f"   Profile: {result.profile is not None}")
            print(f"   Validation: {result.validation is not None}")
            print(f"   Mappings: {len(result.mappings)} fields mapped")
            print(f"   PDF Generated: {result.pdf_base64 is not None}")
            print(f"   Message: {result.message}")
        else:
            print(f"\n❌ Errors: {result.errors}")
            print(f"   Message: {result.message}")
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n📝 FormPilot quick start requires:")
    print("   1. GEMINI_API_KEY set in .env file")
    print("   2. All dependencies installed: pip install -r requirements.txt")
    print("\n")
    
    asyncio.run(main())
