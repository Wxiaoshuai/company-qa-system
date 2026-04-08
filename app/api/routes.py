from fastapi import APIRouter, HTTPException

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