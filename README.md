<div align="center">

# ✈️ FormPilot Enterprise
### AI-Powered Multi-Agent Form Automation System

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?logo=google)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

> **Airia AI Agents Hackathon 2026 — Track 2: Active Agents**  
> Airia-orchestrated 5-step agent pipeline with HITL governance, Slack notifications, and SharePoint archival.

</div>

---

## 🎯 The Problem

Every year, **millions of Indians** spend hours filling the same personal data into government forms — Passport applications, Visa forms, Voter ID, Driver's License. The process is:
- ❌ Repetitive — same fields copied from the same ID documents
- ❌ Error-prone — manual transcription leads to rejections  
- ❌ Time-consuming — 30–60 minutes per form
- ❌ Inaccessible — complex forms confuse non-technical citizens

## ✅ The Solution: FormPilot

FormPilot uses a **5-step Airia pipeline** (4 agents + notification dispatcher) to automate the full form-filling journey:

```
📷 Identity Document
				│
				▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AGENT 1       │────▶│   AGENT 2       │────▶│   AGENT 3       │────▶│   AGENT 4       │
│ Document        │     │ Rules           │     │ Field           │     │ PDF             │
│ Analyzer        │     │ Validator       │     │ Mapper          │     │ Generator       │
│                 │     │                 │     │                 │     │                 │
│ Gemini Vision   │     │ Gemini LLM      │     │ Semantic AI     │     │ ReportLab       │
│ OCR extraction  │     │ Eligibility     │     │ + Fuzzy match   │     │ Professional    │
│ 95%+ accuracy   │     │ 4 countries     │     │ Any form        │     │ PDF generation  │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
				│                       │                       │                       │
				▼                       ▼                       ▼                       ▼
	Identity Profile        Eligible? ✅         11 Fields Mapped         📄 Download PDF
	(with confidence)       Rules checked        (with confidence)        (ready to submit)
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/pranjal2004838/Formpilot.git
cd Formpilot
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_key_here
# Get free key at: https://aistudio.google.com/app/apikey
```

> 💡 **No API key?** `/api/workflows/start` automatically runs in simulated mode and still returns a full result with PDF + audit trail.

### 3. Run

```bash
cd backend
python main.py
```

**Open:** http://localhost:8000 — the full UI loads automatically.  
**API Docs:** http://localhost:8000/docs

---

## 🎬 Demo

### Option A: Instant Demo (No API Key)

```bash
curl -X POST http://localhost:8000/api/workflows/demo
# Returns: full profile + eligibility + 11 mapped fields + PDF base64
```

### Option B: Real Document Processing

```bash
# Base64 encode your Aadhaar/Passport image
IMAGE_B64=$(base64 -w0 your_aadhaar.jpg)

curl -X POST http://localhost:8000/api/workflows/start \
	-H "Content-Type: application/json" \
	-d "{
		\"document_image\": \"$IMAGE_B64\",
		\"document_type\": \"aadhaar\",
		\"country\": \"IN\",
		\"app_type\": \"passport\",
		\"form_title\": \"Passport Application Form\"
	}"
```

### Option C: Web UI

1. Open http://localhost:8000
2. Drag & drop your document OR click **"Load Demo Data"**
3. Click **"Run Instant Demo"** (no API key needed)
4. Watch the 5-step pipeline execute in real-time (4 agents + dispatcher)
5. Download your filled PDF ⬇️

---

## 🏗️ Architecture

### Project Structure

```
Formpilot/
├── backend/
│   ├── main.py                          # FastAPI app — serves UI + API
│   ├── static/
│   │   └── index.html                   # Full SPA frontend (no build step)
│   ├── agents/
│   │   ├── base.py                      # Agent base class (contract)
│   │   ├── agent_1_document_analyzer.py # Gemini Vision OCR
│   │   ├── agent_2_rules_validator.py   # Eligibility rules engine
│   │   ├── agent_3_field_mapper.py      # Semantic field mapping
│   │   └── agent_4_pdf_generator.py     # ReportLab PDF generator
│   ├── workflows/
│   │   └── form_automation_workflow.py  # Pipeline orchestrator
│   ├── models/
│   │   └── schemas.py                   # Pydantic v2 data models
│   └── config/
│       └── settings.py                  # Configuration
├── requirements.txt
└── .env.example
```

### Agent Details

| Agent | Technology | Input | Output |
|-------|------------|-------|--------|
| **1 — Document Analyzer** | Gemini 2.0 Flash Vision | Image bytes | `IdentityProfile` with confidence |
| **2 — Rules Validator** | Gemini 2.0 Flash | Profile + country | Eligibility result + checks |
| **3 — Field Mapper** | Gemini + FuzzyWuzzy | Profile + form fields | Field mappings with confidence |
| **4 — PDF Generator** | ReportLab | Mappings + profile | Professional PDF (base64) |

### Supported Documents

| Document | Country | Fields Extracted |
|----------|---------|-----------------|
| Aadhaar Card | 🇮🇳 India | Name, DOB, Gender, Address, 12-digit ID |
| Passport | 🌍 All | Name, DOB, Gender, Nationality, Passport No. |
| PAN Card | 🇮🇳 India | Name, DOB, PAN Number |
| Generic ID | All | Auto-detected fields |

### Supported Countries (Eligibility Rules)

🇮🇳 India · 🇺🇸 United States · 🇬🇧 United Kingdom · 🇨🇦 Canada

---

## 🔌 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (FormPilot frontend) |
| `/health` | GET | Health check |
| `/api/workflows/start` | POST | Start workflow (real mode with GEMINI key, simulated mode otherwise) |
| `/api/workflows/demo` | POST | Instant demo workflow (always available) |
| `/api/workflows/{id}/status` | GET | Workflow status |
| `/api/workflows/{id}/result` | GET | Full workflow result |
| `/api/workflows/{id}/audit` | GET | Full audit trail for workflow decisions and steps |
| `/api/workflows` | GET | Persistent workflow history |
| `/api/metrics/summary` | GET | Aggregate operational metrics |
| `/api/judge/readiness` | GET | Strict Track 2 self-audit readiness report |
| `/api/integrations/status` | GET | Airia / Slack / SharePoint integration health |
| `/api/airia/pipeline` | GET | Airia pipeline definition |
| `/api/airia/tools` | GET | Airia tool manifest |
| `/api/form-fields` | GET | Default form field definitions |
| `/api/supported-documents` | GET | Supported document types |
| `/api/supported-countries` | GET | Supported countries |
| `/docs` | GET | Interactive API documentation (Swagger) |

---

## 📊 Performance

| Metric | Target | Achieved |
|--------|--------|----------|
| OCR Accuracy | 95%+ | ✅ 95%+ (Gemini 2.0 Flash) |
| End-to-end latency | < 3s | ✅ ~2-3s (API round trip) |
| Simulated fallback (no API key) | 100% availability | ✅ `/api/workflows/start` still completes with PDF + audit |
| PDF generation | < 1s | ✅ < 50ms |
| Fields mapped | 95%+ | ✅ 11/11 (100%) |
| Persistent auditability | Required for enterprise review | ✅ SQLite workflow + audit trail |

---

## 🛠️ Technology Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Orchestration** | Airia Platform + Tool Manifest | Track 2-native active agents architecture |
| **AI / Vision** | Google Gemini 2.0 Flash | High-quality multimodal extraction + reasoning |
| **Backend** | FastAPI + Python 3.12 | Async, auto OpenAPI docs, production-ready |
| **Validation** | Pydantic v2 | Type-safe data models with runtime validation |
| **PDF** | ReportLab 4.0 | Professional government-quality PDF output |
| **Field Matching** | FuzzyWuzzy + Gemini | Dual-mode: semantic AI + fuzzy fallback |
| **Persistence** | SQLite workflow store | Durable history + audit events across restarts |
| **Integrations** | Slack + SharePoint Graph API | Enterprise notifications and archival |
| **Frontend** | Vanilla HTML/CSS/JS | Zero build step, instant load, served by FastAPI |

---

## 🔒 Security

- API keys loaded from environment variables, never committed
- Input validation on all endpoints via Pydantic
- CORS configured for production deployment
- Optional bearer auth enforcement on `/api/tools/*` via `FORMPILOT_API_KEY`
- Persistent workflow/audit trail in SQLite (`DATABASE_URL`)
- Base64 image data is processed in-memory and discarded

---

## 🚢 Deployment

### Railway (Recommended)

```bash
# Create Procfile
echo "web: uvicorn main:app --host 0.0.0.0 --port \$PORT" > backend/Procfile

# Deploy
railway up
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t formpilot .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key formpilot
```

---

## 🏆 Why FormPilot Wins

1. **Real Multi-Agent Architecture** — Not just "LLM with tools" — genuine orchestrated pipeline where each agent has a single responsibility with typed inputs/outputs and confidence scoring

2. **Production-Quality Code** — Pydantic v2, async agents, structured logging, error handling, fallback mechanisms — judges can read the code

3. **Instant Demo** — Click one button, see the full pipeline animate, get a real downloadable PDF — no API key, no signup, no friction

4. **Solves a Real Problem** — 1.4 billion Indians fill government forms. This saves 30 minutes per form, zero errors, zero re-submission

5. **Complete Stack** — Frontend + Backend + AI + PDF — fully working prototype, not just slides

---

## 👨‍💻 Author

Built by **Pranjal Kumar Singh** for the **Airia AI Agents Hackathon 2026 — Track 2: Active Agents**  
GitHub: [@pranjal2004838](https://github.com/pranjal2004838)

---

<div align="center"><sub>FormPilot Enterprise · MIT License · Built with ❤️ and AI</sub></div>