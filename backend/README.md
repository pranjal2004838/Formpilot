# FormPilot Backend

Multi-agent form automation system for government applications.

## Architecture

The backend uses a 4-agent pipeline orchestrated by FastAPI:

1. **Agent 1 - Document Analyzer**: Extracts identity information from document images using Gemini Vision API
2. **Agent 2 - Rules Validator**: Validates extracted identity against government eligibility rules using Gemini API
3. **Agent 3 - Field Mapper**: Maps extracted fields to target form fields using semantic matching with fallback fuzzy matching
4. **Agent 4 - PDF Generator**: Generates professional, government-style PDFs with filled data using ReportLab

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

Get a free Gemini API key from: https://makersuite.google.com/app/apikey

### 3. Run the Server

```bash
cd backend
python main.py
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## API Endpoints

### Start Workflow
```
POST /api/workflows/start
```

Request:
```json
{
  "document_image": "base64-encoded-image",
  "document_type": "passport",
  "form_fields": [],
  "country": "IN",
  "app_type": "visa",
  "form_title": "Visa Application Form"
}
```

Response:
```json
{
  "workflow_id": "uuid",
  "status": "completed",
  "profile": { ... },
  "validation": { ... },
  "mappings": [ ... ],
  "pdf_base64": "..."
}
```

### Get Workflow Status
```
GET /api/workflows/{workflow_id}/status
```

### Get Workflow Result
```
GET /api/workflows/{workflow_id}/result
```

### Cancel Workflow
```
POST /api/workflows/{workflow_id}/cancel
```

### Delete Workflow
```
DELETE /api/workflows/{workflow_id}
```

### Get Configuration
```
GET /api/form-fields
GET /api/supported-documents
GET /api/supported-countries
```

## Architecture Details

### Agent Base Class (`agents/base.py`)
All agents inherit from `Agent` base class which provides:
- Consistent execution interface
- Error handling and logging
- Timing and performance metrics
- Structured output format

### Data Models (`models/schemas.py`)
- `IdentityProfile`: Extracted personal information
- `ValidationResult`: Eligibility check results
- `FormMapping`: Field-to-field mappings
- `WorkflowOutput`: Complete workflow result

### Workflow Orchestration (`workflows/form_automation_workflow.py`)
Sequential execution of all 4 agents with:
- Error handling and fallback behavior
- Detailed logging at each stage
- Performance timing
- Early exit on critical failures

## Running Tests

```bash
pytest backend/tests/ -v
```

## Configuration

See `.env.example` for all available configuration options:

- `GEMINI_API_KEY`: Required for Gemini API access
- `APP_HOST`: Server host (default: 0.0.0.0)
- `APP_PORT`: Server port (default: 8000)
- `FRONTEND_URL`: Frontend origin for CORS
- `DATABASE_URL`: SQLite database path
- `LOG_LEVEL`: Logging level

## Error Handling

All agents implement graceful error handling:

1. **Agent 1 (Document Analyzer)**: Returns error if image cannot be decoded or Gemini API fails
2. **Agent 2 (Rules Validator)**: Returns fallback eligibility=true if validation fails gracefully
3. **Agent 3 (Field Mapper)**: Falls back to fuzzy string matching if Gemini semantic matching fails
4. **Agent 4 (PDF Generator)**: Returns error if PDF generation fails

The workflow continues when an error is recoverable but stops early if a critical stage fails.

## Performance

Expected performance per workflow:
- Document Analysis (Agent 1): 2-3 seconds
- Rules Validation (Agent 2): 1-2 seconds
- Field Mapping (Agent 3): 1-2 seconds
- PDF Generation (Agent 4): 1 second

**Total end-to-end time: 5-8 seconds**

## Scaling Considerations

For production:
1. Replace in-memory workflow state with database (PostgreSQL)
2. Add Redis caching for frequent queries
3. Implement async job queue (Celery with Redis)
4. Add authentication/authorization
5. Implement workflow webhooks for async completion
6. Monitor with Prometheus/Grafana
7. Add rate limiting

## Development

### Adding New Agents

1. Create new file in `backend/agents/agent_N_*.py`
2. Inherit from `Agent` base class
3. Implement `async execute(input_data: AgentInput) -> AgentOutput`
4. Add to workflow in `workflows/form_automation_workflow.py`
5. Add tests in `backend/tests/test_agent_N.py`

### Adding New Document Types

Update `Agent 1` to support new document types:
1. Add document type to `_get_extraction_prompt()`
2. Create specialized extraction prompt for new type
3. Test with sample documents

## Troubleshooting

### "GEMINI_API_KEY not set"
- Set `GEMINI_API_KEY` in `.env` file
- Restart the server

### "Workflow failed: Document analysis failed"
- Check that document image is properly base64 encoded
- Verify image quality (clear, well-lit, readable)
- Check that `document_type` matches the actual document

### "JSON parsing error in Agent X"
- This is normal - agents have fallback mechanisms
- Check logs for specific parsing error
- Verify Gemini API response format

## License

MIT
