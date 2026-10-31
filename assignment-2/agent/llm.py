"""LLM factory and wrapper with Pydantic v2 safe attribute setting and rate-limit tolerance."""
import logging

from config import settings

logger = logging.getLogger(__name__)


def get_llm(model: str = None, api_key: str = None, temperature: float = 0.0):
    """Instantiate ChatGroq with safe trace labeling."""
    key = api_key or settings.groq_api_key()
    if not key:
        return None
    try:
        from langchain_groq import ChatGroq

        model_name = model or settings.groq_model()
        llm = ChatGroq(model=model_name, api_key=key, temperature=temperature)
        try:
            object.__setattr__(llm, "model_name_for_trace", model_name)
        except Exception:
            pass
        return llm
    except Exception as exc:
        logger.warning("Could not initialize ChatGroq: %s", exc)
        return None


def model_label(llm) -> str:
    if llm is None:
        return "offline planner (no LLM)"
    if hasattr(llm, "model_name_for_trace"):
        return llm.model_name_for_trace
    if hasattr(llm, "model_name"):
        return llm.model_name
    if hasattr(llm, "model"):
        return llm.model
    return type(llm).__name__
