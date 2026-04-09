from app.core.config import settings
from app.services.llamaindex_qa_service import LlamaIndexQAService
from app.services.native_qa_service import NativeQAService, QAResult


def _normalize_engine(engine: str) -> str:
    normalized = (engine or "auto").strip().lower()
    if normalized not in {"auto", "native", "llamaindex"}:
        return "auto"
    return normalized


class QAServiceFacade:
    def __init__(self) -> None:
        self._native = NativeQAService()
        self._llamaindex = LlamaIndexQAService()

    def _select_backend(self):
        engine = _normalize_engine(settings.rag_engine)
        if engine == "native":
            return self._native

        if self._llamaindex.is_available():
            return self._llamaindex

        if engine == "llamaindex":
            raise RuntimeError(
                "RAG_ENGINE is set to llamaindex, but LlamaIndex is not installed. "
                "Install the optional LlamaIndex dependencies or switch RAG_ENGINE to native/auto."
            )
        return self._native

    def answer(self, question: str) -> QAResult:
        return self._select_backend().answer(question)

    def stream_answer(self, question: str):
        return self._select_backend().stream_answer(question)


qa_service = QAServiceFacade()
