from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")


class AskResponse(BaseModel):
    answer: str
    references: list[str]