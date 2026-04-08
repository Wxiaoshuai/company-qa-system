import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import AskRequest, AskResponse
from app.services.qa_service import qa_service

router = APIRouter(prefix="/api/v1/qa", tags=["qa"])


@router.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    try:
        result = qa_service.answer(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AskResponse(answer=result.answer, references=result.references)


def _sse_event(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
def stream_question(payload: AskRequest) -> StreamingResponse:
    try:
        answer_stream, references = qa_service.stream_answer(payload.question)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def event_stream():
        try:
            for token in answer_stream:
                yield _sse_event("token", token)
            yield _sse_event("references", references)
            yield _sse_event("done", "ok")
        except Exception as exc:
            yield _sse_event("error", str(exc))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
