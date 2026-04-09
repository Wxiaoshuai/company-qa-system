# company-qa-system

Company QA system with a practical RAG baseline (FastAPI + local vector index + optional LlamaIndex acceleration).

## Project Structure

```text
company-qa-system/
  app/
    api/routes.py
    core/config.py
    models/schemas.py
    services/qa_service.py
    main.py
  data/
    docs/                # Put your source docs here (.txt/.md/.markdown)
    vector_store/        # Generated index.json after ingestion
  scripts/
    ingest.py
  .env.example
  .gitignore
  requirements.txt
  requirements-llamaindex.txt
```

## Setup

1. Create environment and install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional LlamaIndex enhancement:

```powershell
pip install -r requirements-llamaindex.txt
```

2. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Required variables in `.env`:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (optional, supports OpenAI-compatible gateways)

Optional RAG variables:

- `RAG_ENGINE=auto`
- `RAG_LLAMAINDEX_PERSIST_DIR=data/vector_store/llamaindex`

3. Put docs under `data/docs/` (UTF-8 `.txt`/`.md`)

4. Build vector index

```powershell
python scripts/ingest.py
```

If optional LlamaIndex dependencies are installed, the same command will also persist a LlamaIndex index.

5. Start API

```powershell
uvicorn app.main:app --reload --port 8000
```

## API

- Chat UI: `GET /`
- Health: `GET /health`
- Ask: `POST /api/v1/qa/ask`

Request body:

```json
{
  "question": "What is our annual leave policy?"
}
```

Response body:

```json
{
  "answer": "...",
  "references": [
    "data/docs/hr_policy.md#3",
    "data/docs/employee_handbook.md#7"
  ]
}
```

Test:
```powershell
python -c "import requests; response = requests.post('http://127.0.0.1:8000/api/v1/qa/ask', json={'question': 'What is the annual leave policy?'}); print(response.json())"
```

Open the chat page:
```text
http://127.0.0.1:8000/
```

The chat page:

- works on desktop browsers and mobile H5 browsers
- includes welcome question shortcuts for quick start
- stores chat history in the current browser via `localStorage`
- streams answers progressively from the server
- shows response references in a collapsible section

## Notes

- The project supports two RAG backends:
  - native JSON vector retrieval for maximum compatibility
  - optional LlamaIndex query engine, automatically preferred in `RAG_ENGINE=auto`
- For production, replace index storage with a vector database and add auth, logging, and evaluation.

## Deployment

- Alibaba Cloud ECS deployment guide: `DEPLOY_ALIYUN.md`
