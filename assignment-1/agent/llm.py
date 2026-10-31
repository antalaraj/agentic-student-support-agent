"""LLM factory (Groq via langchain-groq)."""
import logging

from config import settings

logger = logging.getLogger(__name__)


def resolve_model(api_key: str) -> str:
    """Use the configured model if the account lists it; otherwise pick the first preferred model that is
    available. Falls back to the configured name if the model list cannot be fetched."""
    wanted = settings.groq_model()
    try:
        from groq import Groq

        available = {m.id for m in Groq(api_key=api_key).models.list().data}
        if wanted in available:
            return wanted
        for name in settings.PREFERRED_GROQ_MODELS:
            if name in available:
                logger.warning("Model %s not available; using %s", wanted, name)
                return name
    except Exception as exc:
        logger.warning("Could not list Groq models (%s); using configured model %s", type(exc).__name__, wanted)
    return wanted


def get_llm():
    """Return a ChatGroq instance, or None when no API key is configured (-> offline mode)."""
    key = settings.groq_api_key()
    if not key:
        return None
    from langchain_groq import ChatGroq

    model = resolve_model(key)
    llm = ChatGroq(model=model, api_key=key, temperature=0, max_retries=1, timeout=30)
    try:
        object.__setattr__(llm, "model_name_for_trace", model)
    except Exception:
        pass
    return llm


def model_label(llm) -> str:
    if llm is None:
        from agent.offline_llm import OfflinePlanner
        return OfflinePlanner.model_name
    return getattr(llm, "model_name_for_trace", None) or getattr(llm, "model_name", None) or getattr(llm, "model", "unknown")
