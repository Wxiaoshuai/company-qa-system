# company-qa-system

Company QA system with a practical RAG baseline (FastAPI + local vector index + OpenAI).

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
```

## Setup

1. Create environment and install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Required variables in `.env`:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (optional, only if your gateway requires it)

3. Put docs under `data/docs/` (UTF-8 `.txt`/`.md`)

4. Build vector index

```powershell
python scripts/ingest.py
```

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

- Current retriever uses cosine similarity over local JSON vectors.
- For production, replace index storage with a vector database and add auth, logging, and evaluation.
