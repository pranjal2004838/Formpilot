# FormPilot Enterprise — Execution & Implementation Plan
## Day-by-Day Breakdown with Code Steps

---

## Quick Decision Checklist (Decide First)

Before I start coding, answer these to lock in scope:

```
SCOPE DECISIONS:
[ ] AI Model: OpenAI GPT-4 vs Claude 3 Opus?
[ ] Government Rules: India-only OR India+US/UK/Canada in MVP?
[ ] Form Support: PDF-only OR also JSON schema/HTML?
[ ] Temporal: Cloud (managed) OR Local executor?
[ ] Storage: SharePoint OR AWS S3 (simpler)?
[ ] Database: PostgreSQL OR SQLite (faster for hackathon)?

TIMELINE CONSTRAINTS:
[ ] Team Size: Solo Claude OR with human help?
[ ] Hours available: 8h/day OR 16h/day?
[ ] Demo Priority: Polished UI OR Robust cores?
```

---

## Full Implementation Roadmap

### PHASE 1: Project Setup (3 hours | Day 1)

#### 1.1 Initialize Backend
```bash
# Create Python project
mkdir formpilot-backend
cd formpilot-backend

# Virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install core dependencies
pip install fastapi uvicorn pydantic python-dotenv

# Install agent dependencies
pip install temporal-io openai requests

# Install PDF dependencies
pip install PyPDF2 aiofiles

# Install form handling
pip install python-multipart

# Create directory structure
mkdir -p agents/{agent_1,agent_2,agent_3,agent_4}
mkdir -p workflows
mkdir -p integrations
mkdir -p models
mkdir -p utils
```

#### 1.2 Initialize Frontend
```bash
cd ../
npx create-next-app@latest formpilot-frontend \
  --typescript \
  --tailwind \
  --app

cd formpilot-frontend
npm install shadcn-ui lucide-react axios react-query framer-motion
```

#### 1.3 Environment Setup
```bash
# .env.local (backend)
OPENAI_API_KEY=sk-...
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
SHAREPOINT_CLIENT_ID=...
SHAREPOINT_CLIENT_SECRET=...
SHAREPOINT_TENANT=...
DATABASE_URL=postgresql://user:pass@localhost/formpilot
TEMPORAL_HOST=localhost
TEMPORAL_PORT=7233

# Frontend .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### 1.4 Database Setup (PostgreSQL)
```sql
-- Initialize schema
CREATE TABLE audit_logs (
  id SERIAL PRIMARY KEY,
  workflow_id UUID,
  agent_name VARCHAR(50),
  status VARCHAR(50),
  input_data JSONB,
  output_data JSONB,
  timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE form_mappings (
  id SERIAL PRIMARY KEY,
  workflow_id UUID,
  form_fields JSONB,
  mapped_values JSONB,
  confidence_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE extracted_profiles (
  id SERIAL PRIMARY KEY,
  workflow_id UUID,
  profile_data JSONB,
  document_type VARCHAR(50),
  confidence_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### PHASE 2: Agent 1 — Document Analyzer (16 hours | Days 2-3)

#### 2.1 Basic OCR Pipeline
```python
# backends/agents/agent_1/ocr_extractor.py

from fastapi import UploadFile
from openai import OpenAI
import base64
import json
from pydantic import BaseModel

class IdentityProfile(BaseModel):
    fullName: str
    dob: str
    gender: str
    address: dict
    documentId: str
    documentType: str
    confidence: float

class DocumentAnalyzer:
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
    
    async def extract_from_image(self, image_file: UploadFile, doc_type: str) -> IdentityProfile:
        """
        Extract identity data from document image using Claude Vision API
        """
        # Read image
        image_data = await image_file.read()
        base64_image = base64.b64encode(image_data).decode()
        
        # Build prompt based on document type
        if doc_type == "aadhaar":
            extraction_prompt = self._aadhaar_extraction_prompt()
        elif doc_type == "passport":
            extraction_prompt = self._passport_extraction_prompt()
        else:
            extraction_prompt = self._generic_extraction_prompt()
        
        # Call OpenAI Vision API
        response = self.client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": extraction_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        # Parse response
        extracted_json = json.loads(response.choices[0].message.content)
        
        # Return structured profile
        return IdentityProfile(**extracted_json)
    
    def _aadhaar_extraction_prompt(self) -> str:
        return """
        Extract the following fields from this Aadhaar card image:
        - Full Name (as shown)
        - Date of Birth (DD/MM/YYYY format)
        - Gender (Male/Female/Other)
        - Address (street, city, state, pincode)
        - Aadhaar Number (12 digits)
        
        Return ONLY valid JSON with these fields and a confidence score (0-1).
        Example format:
        {
            "fullName": "...",
            "dob": "...",
            "gender": "...",
            "address": {"street": "...", "city": "...", "state": "...", "pincode": "..."},
            "documentId": "...",
            "documentType": "Aadhaar",
            "confidence": 0.95
        }
        """
    
    def _passport_extraction_prompt(self) -> str:
        return """
        Extract the following fields from this Passport image:
        - Full Name
        - Date of Birth (DD/MM/YYYY)
        - Gender
        - Address (full address if visible)
        - Passport Number
        - Nationality
        
        Return ONLY valid JSON format with confidence score.
        """
    
    def _generic_extraction_prompt(self) -> str:
        return """
        Extract all personal identity information visible in this document:
        - Full Name
        - Date of Birth
        - Gender
        - Address
        - Document ID/Number
        - Document Type
        
        Return as JSON with confidence score.
        """

# FastAPI endpoint
from fastapi import FastAPI, UploadFile, File

app = FastAPI()
analyzer = DocumentAnalyzer(openai_api_key="sk-...")

@app.post("/api/agents/document-analyzer/extract")
async def extract_identity(
    file: UploadFile = File(...),
    doc_type: str = "aadhaar"
):
    profile = await analyzer.extract_from_image(file, doc_type)
    return {
        "status": "success",
        "profile": profile.dict(),
        "timestamp": datetime.now().isoformat()
    }
```

#### 2.2 Validation & Cleanup
```python
# backends/agents/agent_1/validators.py

import re
from datetime import datetime

class IdentityValidator:
    @staticmethod
    def validate_aadhaar(aadhaar: str) -> bool:
        """Validate Aadhaar format: 12 digits"""
        return bool(re.match(r'^\d{12}$', aadhaar))
    
    @staticmethod
    def validate_dob(dob: str) -> bool:
        """Validate date format: DD/MM/YYYY or YYYY-MM-DD"""
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                datetime.strptime(dob, fmt)
                return True
            except ValueError:
                continue
        return False
    
    @staticmethod
    def validate_pincode(pincode: str) -> bool:
        """Validate Indian pincode: 6 digits"""
        return bool(re.match(r'^\d{6}$', pincode))
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate Indian phone: 10 digits"""
        return bool(re.match(r'^\d{10}$', phone.replace(' ', '').replace('-', '')))
    
    @staticmethod
    def validate_pan(pan: str) -> bool:
        """Validate PAN format: 10 chars (AAAAA0000A)"""
        return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan))

# Clean and normalize extracted data
class DataCleaner:
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Remove spaces/dashes, keep only digits"""
        return re.sub(r'\D', '', phone)
    
    @staticmethod
    def normalize_dob(dob: str) -> str:
        """Convert all dates to YYYY-MM-DD"""
        for fmt in ('%d/%m/%Y', '%d-%m-%Y'):
            try:
                dt = datetime.strptime(dob, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return dob
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Title case, remove extra spaces"""
        return ' '.join(name.strip().split()).title()
    
    @staticmethod
    def normalize_address(address_parts: dict) -> dict:
        """Clean address components"""
        return {
            k: ' '.join(str(v).strip().split()).title() 
            for k, v in address_parts.items()
        }
```

#### 2.3 Agent 1 Worker (Temporal)
```python
# backends/agents/agent_1/worker.py

from temporalio import workflow, activity
from typing import Dict, Any
import json

@activity.defn
async def extract_document(
    file_base64: str,
    doc_type: str
) -> Dict[str, Any]:
    """Activity: Extract identity from document"""
    analyzer = DocumentAnalyzer(openai_api_key="sk-...")
    # Logic here
    return extracted_profile

@workflow.defn
class DocumentAnalysisWorkflow:
    @workflow.run
    async def run(self, document_data: dict) -> dict:
        result = await workflow.execute_activity(
            extract_document,
            args=[document_data['file_base64'], document_data['doc_type']],
            start_to_close_timeout=timedelta(seconds=60)
        )
        return result
```

---

### PHASE 3: Agent 2 — Rules Validator (12 hours | Days 3-4)

#### 3.1 Rules Database (YAML)
```yaml
# backends/config/rules.yaml

countries:
  india:
    passport:
      min_age: 18
      max_age: null
      citizenship: "Indian"
      required_docs:
        - address_proof
        - id_proof
        - birth_certificate
        - police_verification
      fields:
        - fullName
        - dob
        - gender
        - address
        - phone
    
    visa:
      us:
        min_age: 18
        visa_validity_required: false
        required_docs:
          - passport
          - financial_proof
          - job_letter
      uk:
        min_age: 18
        visa_validity_required: false
      canada:
        min_age: 18

  us:
    visa:
      min_age: 0
      citizenship_countries:
        - all
```

#### 3.2 Validation Engine
```python
# backends/agents/agent_2/rules_validator.py

import yaml
from datetime import datetime, timedelta
from pydantic import BaseModel

class ValidationResult(BaseModel):
    eligible: bool
    validationResults: list
    missingFields: list
    notes: str

class RulesValidator:
    def __init__(self, rules_path: str = "config/rules.yaml"):
        with open(rules_path) as f:
            self.rules = yaml.safe_load(f)
    
    async def validate(
        self,
        profile: dict,
        country: str,
        app_type: str,
        visa_country: str = None
    ) -> ValidationResult:
        """
        Validate profile against country/application rules
        """
        validation_results = []
        missing_fields = []
        
        # Get applicable rules
        if visa_country:
            rules = self.rules['countries'][country]['visa'][visa_country]
        else:
            rules = self.rules['countries'][country][app_type]
        
        # Age check
        if 'min_age' in rules:
            age = self._calculate_age(profile['dob'])
            valid = age >= rules['min_age']
            validation_results.append({
                'field': 'age',
                'valid': valid,
                'requirement': f"Min age {rules['min_age']}",
                'value': age
            })
        
        # Required fields check
        required = rules.get('required_docs', [])
        for field in required:
            has_field = field in profile
            validation_results.append({
                'field': field,
                'valid': has_field,
                'requirement': f"Must provide {field}"
            })
            if not has_field:
                missing_fields.append(field)
        
        # Overall eligibility
        eligible = all(v['valid'] for v in validation_results)
        
        return ValidationResult(
            eligible=eligible,
            validationResults=validation_results,
            missingFields=missing_fields,
            notes=self._generate_notes(eligible, app_type, country)
        )
    
    @staticmethod
    def _calculate_age(dob: str) -> int:
        """Calculate age from DOB"""
        birth_date = datetime.strptime(dob, '%Y-%m-%d')
        today = datetime.now()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
    
    @staticmethod
    def _generate_notes(eligible: bool, app_type: str, country: str) -> str:
        if eligible:
            return f"User eligible for {country} {app_type}"
        else:
            return f"User not eligible for {country} {app_type}. Review missing documents."

# FastAPI endpoint
@app.post("/api/agents/rules-validator/validate")
async def validate_eligibility(
    profile: dict,
    country: str,
    app_type: str,
    visa_country: str = None
):
    validator = RulesValidator()
    result = await validator.validate(profile, country, app_type, visa_country)
    return result.dict()
```

---

### PHASE 4: Agent 3 — Form Field Mapper (14 hours | Days 4-5)

#### 4.1 Form Parser
```python
# backends/agents/agent_3/form_parser.py

import PyPDF2
from pydantic import BaseModel
from typing import List

class FormField(BaseModel):
    name: str
    type: str  # text, date, select, checkbox
    required: bool
    parent_label: str = None  # "First Name" label near field

class FormParser:
    async def parse_pdf_form(self, pdf_file_bytes: bytes) -> List[FormField]:
        """Extract form fields from PDF"""
        pdf_reader = PyPDF2.PdfReader(file_from_bytes := pdf_file_bytes)
        form_fields = []
        
        if "/AcroForm" in pdf_reader.pages[0]:
            acro_form = pdf_reader.pages[0]["/AcroForm"]
            
            for field in acro_form["/Fields"]:
                field_obj = field.get_object()
                form_fields.append(FormField(
                    name=field_obj.get("/T", "").strip("()"),
                    type=field_obj.get("/FT", "").strip("()") or "text",
                    required=field_obj.get("/Ff", 0) & 2 == 0
                ))
        
        return form_fields
    
    async def parse_json_schema(self, schema: dict) -> List[FormField]:
        """Parse form fields from JSON schema"""
        fields = []
        for field_name, field_config in schema.items():
            fields.append(FormField(
                name=field_name,
                type=field_config.get('type', 'text'),
                required=field_config.get('required', False),
                parent_label=field_config.get('label')
            ))
        return fields
```

#### 4.2 Semantic Field Matcher (Claude)
```python
# backends/agents/agent_3/field_matcher.py

from openai import OpenAI
import json
from fuzzywuzzy import fuzz

class FieldMatcher:
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
    
    async def match_fields(
        self,
        profile: dict,
        form_fields: list
    ) -> dict:
        """
        Match extracted identity fields to form fields
        """
        # Build prompt for Claude
        profile_str = json.dumps(profile, indent=2)
        form_fields_str = json.dumps(
            [{'name': f['name'], 'label': f.get('parent_label', '')} for f in form_fields],
            indent=2
        )
        
        prompt = f"""
        I have extracted identity information from a document:
        {profile_str}
        
        And a form with these fields:
        {form_fields_str}
        
        Match each form field to the extracted data.
        For each form field, provide:
        1. The extracted field name it maps to
        2. The transformed value
        3. Any transformation needed (date format, address split, etc.)
        4. Confidence score (0-1)
        
        Return ONLY valid JSON array:
        [
            {{
                "formFieldName": "...",
                "extractedFieldName": "...",
                "value": "...",
                "transformation": "none|format_conversion|split|join|...",
                "confidence": 0.95
            }},
            ...
        ]
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        mappings = json.loads(response.choices[0].message.content)
        
        return {
            "mappings": mappings,
            "readyToFill": all(m['confidence'] > 0.7 for m in mappings),
            "confidence": sum(m['confidence'] for m in mappings) / len(mappings)
        }
    
    def fuzzy_match(self, field_name: str, available_fields: list) -> tuple:
        """Fallback fuzzy string matching"""
        best_match = None
        best_score = 0
        
        for available_field in available_fields:
            score = fuzz.token_set_ratio(field_name.lower(), available_field.lower())
            if score > best_score:
                best_score = score
                best_match = available_field
        
        return best_match, best_score / 100.0
```

#### 4.3 Data Transformation
```python
# backends/agents/agent_3/transformers.py

class DataTransformer:
    @staticmethod
    def split_fullname(fullname: str) -> tuple:
        """Split full name to firstName, lastName"""
        parts = fullname.strip().split()
        if len(parts) == 0:
            return "", ""
        elif len(parts) == 1:
            return parts[0], ""
        else:
            return parts[0], " ".join(parts[1:])
    
    @staticmethod
    def format_date(date_str: str, from_fmt: str, to_fmt: str) -> str:
        """Convert date format"""
        from datetime import datetime
        dt = datetime.strptime(date_str, from_fmt)
        return dt.strftime(to_fmt)
    
    @staticmethod
    def split_address(address: dict, target_fields: list) -> dict:
        """Split address into target fields"""
        result = {}
        
        if 'street' in target_fields:
            result['street'] = address.get('street', '')
        if 'city' in target_fields:
            result['city'] = address.get('city', '')
        if 'state' in target_fields:
            result['state'] = address.get('state', '')
        if 'pincode' in target_fields or 'zip' in target_fields:
            result['pincode'] = address.get('pincode', '')
        
        # If single address field needed
        if 'address' in target_fields and len(target_fields) == 1:
            result['address'] = ' '.join(filter(None, [
                address.get('street'),
                address.get('city'),
                address.get('state'),
                address.get('pincode')
            ]))
        
        return result
```

---

### PHASE 5: Agent 4 — PDF Generator (12 hours | Days 5-6)

#### 5.1 PDF Form Filling
```python
# backends/agents/agent_4/pdf_generator.py

import PyPDF2
from PyPDF2 import PdfWriter, PdfReader
from io import BytesIO

class PDFFormFiller:
    @staticmethod
    def fill_pdf_form(
        pdf_bytes: bytes,
        data: dict
    ) -> bytes:
        """Fill PDF form with extracted data"""
        reader = PdfReader(BytesIO(pdf_bytes))
        writer = PdfWriter()
        
        # Copy all pages
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            writer.add_page(page)
        
        # Update form field data
        if "/AcroForm" in reader.pages[0]:
            writer.update_page_form_field_values(
                writer.pages[0],
                data
            )
        
        # Output
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        
        return output.getvalue()
```

#### 5.2 SharePoint Integration
```python
# backends/integrations/sharepoint.py

from microsoft.graph.generated import GraphServiceClient
from azure.identity import ClientSecretCredential
from io import BytesIO

class SharePointUploader:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.credential = ClientSecretCredential(
            tenant_id,
            client_id,
            client_secret
        )
        self.client = GraphServiceClient(self.credential)
    
    async def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        site_name: str,
        folder_name: str = "FormPilot Generated"
    ) -> str:
        """Upload filled PDF to SharePoint"""
        try:
            # Get site
            sites = await self.client.sites.get()
            
            # Upload file
            upload_session = await self.client.sites[site_name].drive.items.root[folder_name].create_upload_session
            
            # Return link
            return f"https://sharepoint.com/{site_name}/Forms/{filename}"
        except Exception as e:
            print(f"SharePoint upload failed: {e}")
            return None
```

#### 5.3 Slack Notification
```python
# backends/integrations/slack.py

import aiohttp
import json

class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def notify_completion(
        self,
        workflow_id: str,
        filename: str,
        status: str = "success",
        sharepoint_link: str = None
    ):
        """Send Slack notification when form is completed"""
        message = {
            "text": "FormPilot: Form Automation Complete ✓",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*FormPilot Enterprise*\n✅ Form automation completed\n\n*File:* {filename}\n*Workflow:* {workflow_id}"
                    }
                }
            ]
        }
        
        if sharepoint_link:
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📁 [View in SharePoint]({sharepoint_link})"
                }
            })
        
        async with aiohttp.ClientSession() as session:
            await session.post(self.webhook_url, json=message)
```

---

### PHASE 6: Temporal Orchestration (10 hours | Days 6-7)

#### 6.1 Main Workflow
```python
# backends/workflows/form_automation_workflow.py

from temporalio import workflow, activity
from datetime import timedelta
import json
import uuid

@activity.defn
async def agent_1_extract(document_data: dict):
    """Workflow activity: Document extraction"""
    pass

@activity.defn
async def agent_2_validate(profile: dict, context: dict):
    """Workflow activity: Rules validation"""
    pass

@activity.defn
async def agent_3_map(profile: dict, form_fields: list):
    """Workflow activity: Field mapping"""
    pass

@activity.defn
async def agent_4_generate(mappings: dict, pdf_bytes: bytes):
    """Workflow activity: PDF generation"""
    pass

@activity.defn
async def upload_and_notify(pdf_bytes: bytes, filename: str, slack_url: str):
    """Workflow activity: Upload to SharePoint + notify Slack"""
    pass

@workflow.defn
class FormAutomationWorkflow:
    @workflow.run
    async def run(self, workflow_input: dict) -> dict:
        """
        Main orchestration workflow
        
        Input:
        {
            "document_file": base64,
            "document_type": "aadhaar",
            "form_file": base64 | json_schema,
            "country": "india",
            "app_type": "passport",
            "visa_country": "us"  # optional
        }
        """
        workflow_id = str(uuid.uuid4())
        
        # Step 1: Extract identity from document
        try:
            profile = await workflow.execute_activity(
                agent_1_extract,
                args=[workflow_input['document_file'], workflow_input['document_type']],
                start_to_close_timeout=timedelta(seconds=60)
            )
        except Exception as e:
            return {"status": "error", "message": f"Document extraction failed: {e}"}
        
        # Step 2: Validate eligibility
        validation_result = await workflow.execute_activity(
            agent_2_validate,
            args=[profile, workflow_input],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        if not validation_result['eligible']:
            return {
                "status": "ineligible",
                "reason": validation_result['notes'],
                "missing_fields": validation_result['missingFields']
            }
        
        # Step 3: Parse form and map fields
        form_mappings = await workflow.execute_activity(
            agent_3_map,
            args=[profile, workflow_input['form_file']],
            start_to_close_timeout=timedelta(seconds=45)
        )
        
        # Step 4: Generate filled PDF
        filled_pdf = await workflow.execute_activity(
            agent_4_generate,
            args=[form_mappings, workflow_input['form_file']],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 5: Upload and notify
        await workflow.execute_activity(
            upload_and_notify,
            args=[filled_pdf, f"{workflow_id}.pdf", workflow_input.get('slack_webhook')],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "profile": profile,
            "mappings": form_mappings,
            "pdf_url": f"/downloads/{workflow_id}.pdf"
        }
```

---

### PHASE 7: Next.js Frontend (12 hours | Days 6-7)

#### 7.1 Upload Interface
```tsx
// frontend/app/page.tsx

"use client";
import { useState } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle } from "lucide-react";
import axios from "axios";

export default function HomePage() {
  const [step, setStep] = useState(1);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [formFile, setFormFile] = useState<File | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDocumentUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setDocumentFile(file);
  };

  const handleFormUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setFormFile(file);
  };

  const startWorkflow = async () => {
    if (!documentFile || !formFile) {
      setError("Please upload both document and form");
      return;
    }

    setLoading(true);
    try {
      const docBase64 = await fileToBase64(documentFile);
      const formBase64 = await fileToBase64(formFile);

      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/workflows/start`,
        {
          document_file: docBase64,
          document_type: "aadhaar",
          form_file: formBase64,
          country: "india",
          app_type: "passport",
        }
      );

      setWorkflowId(response.data.workflow_id);
      setStep(2);
    } catch (err) {
      setError("Workflow failed to start");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 to-blue-900 p-8">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white mb-2">FormPilot Enterprise</h1>
          <p className="text-blue-100">Automate bureaucratic form workflows with AI agents</p>
        </div>

        {/* Step Indicator */}
        <div className="flex justify-between mb-8">
          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              className={`flex-1 h-2 mx-1 rounded ${
                step >= s ? "bg-green-500" : "bg-blue-300"
              }`}
            />
          ))}
        </div>

        {/* Step 1: Upload Files */}
        {step === 1 && (
          <div className="bg-white rounded-lg shadow-xl p-8 space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">Upload Documents</h2>

            {/* Document Upload */}
            <div className="border-2 border-dashed border-blue-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 transition">
              <Upload className="mx-auto mb-4 text-blue-500" size={40} />
              <p className="text-gray-700 font-medium mb-2">Upload Identity Document</p>
              <p className="text-gray-500 text-sm mb-4">Aadhaar, Passport, or PAN</p>
              <input
                type="file"
                accept="image/*"
                onChange={handleDocumentUpload}
                className="sr-only"
                id="doc-upload"
              />
              <label htmlFor="doc-upload" className="text-blue-600 cursor-pointer hover:underline">
                Choose file
              </label>
              {documentFile && (
                <p className="mt-4 text-green-600">✓ {documentFile.name}</p>
              )}
            </div>

            {/* Form Upload */}
            <div className="border-2 border-dashed border-blue-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 transition">
              <FileText className="mx-auto mb-4 text-blue-500" size={40} />
              <p className="text-gray-700 font-medium mb-2">Upload Form Template</p>
              <p className="text-gray-500 text-sm mb-4">PDF form or JSON schema</p>
              <input
                type="file"
                accept=".pdf"
                onChange={handleFormUpload}
                className="sr-only"
                id="form-upload"
              />
              <label htmlFor="form-upload" className="text-blue-600 cursor-pointer hover:underline">
                Choose file
              </label>
              {formFile && <p className="mt-4 text-green-600">✓ {formFile.name}</p>}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded p-4 flex items-start">
                <AlertCircle className="text-red-500 mr-3 mt-0.5" size={20} />
                <p className="text-red-700">{error}</p>
              </div>
            )}

            <button
              onClick={startWorkflow}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-3 rounded-lg transition"
            >
              {loading ? "Processing..." : "Start Workflow"}
            </button>
          </div>
        )}

        {/* Step 2: Workflow Status */}
        {step === 2 && workflowId && (
          <WorkflowStatus workflowId={workflowId} onComplete={() => setStep(3)} />
        )}

        {/* Step 3: Results */}
        {step === 3 && <ResultsView />}
      </div>
    </div>
  );
}

// Helper to convert file to base64
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
  });
}
```

#### 7.2 Workflow Status Component
```tsx
// frontend/app/components/WorkflowStatus.tsx

"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";

interface AgentStatus {
  agent: string;
  status: "pending" | "running" | "completed" | "failed";
  duration?: number;
}

export function WorkflowStatus({
  workflowId,
  onComplete,
}: {
  workflowId: string;
  onComplete: () => void;
}) {
  const [statuses, setStatuses] = useState<AgentStatus[]>([
    { agent: "Document Analyzer", status: "pending" },
    { agent: "Rules Validator", status: "pending" },
    { agent: "Field Mapper", status: "pending" },
    { agent: "PDF Generator", status: "pending" },
  ]);

  useEffect(() => {
    const poll = async () => {
      try {
        const response = await axios.get(
          `${process.env.NEXT_PUBLIC_API_URL}/workflows/${workflowId}/status`
        );

        if (response.data.status === "completed") {
          setStatuses((prev) =>
            prev.map((s) => ({
              ...s,
              status: "completed" as const,
            }))
          );
          setTimeout(onComplete, 1000);
        } else {
          // Update statuses based on response
          setStatuses(response.data.agents);
        }
      } catch (error) {
        console.error("Poll failed:", error);
      }
    };

    const interval = setInterval(poll, 500);
    return () => clearInterval(interval);
  }, [workflowId, onComplete]);

  return (
    <div className="bg-white rounded-lg shadow-xl p-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-8">Processing Workflow</h2>

      <div className="space-y-4">
        {statuses.map((agent, idx) => (
          <motion.div
            key={agent.agent}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.2 }}
            className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg"
          >
            <div className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-100">
              {agent.status === "completed" ? (
                <span className="text-green-600 font-bold">✓</span>
              ) : agent.status === "running" ? (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity }}
                  className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full"
                />
              ) : (
                <span className="text-gray-400 text-sm">◯</span>
              )}
            </div>
            <div className="flex-1">
              <p className="font-medium text-gray-900">{agent.agent}</p>
              <p className="text-sm text-gray-500 capitalize">{agent.status}</p>
            </div>
            {agent.duration && (
              <p className="text-sm text-gray-500">{agent.duration}s</p>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
```

---

## Summary: Files to Create

```plaintext
formpilot-backend/
├── agents/
│   ├── agent_1_document_analyzer.py
│   ├── agent_2_rules_validator.py
│   ├── agent_3_field_mapper.py
│   └── agent_4_pdf_generator.py
├── workflows/
│   └── form_automation_workflow.py
├── integrations/
│   ├── sharepoint.py
│   └── slack.py
├── models/
│   └── schemas.py
├── utils/
│   ├── validators.py
│   └── transformers.py
├── config/
│   └── rules.yaml
├── main.py (FastAPI server)
└── requirements.txt

formpilot-frontend/
├── app/
│   ├── page.tsx (main upload)
│   ├── dashboard.tsx (results)
│   └── components/
│       └── WorkflowStatus.tsx
├── .env.local
└── package.json
```

---

## Next Action

Ready to proceed? I'll start with:
1. **Backend scaffolding** (FastAPI + project structure)
2. **Agent 1** (Document OCR)
3. **Agent 2** (Rules validation)
4. Complete the chain...

**Confirm and I'll begin coding immediately.**

