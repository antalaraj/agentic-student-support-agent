"""Tool registry. The functions hold the real logic; StructuredTool wraps them so LangChain/LangGraph
can bind them to the LLM (name + description + typed arguments schema)."""
from langchain_core.tools import StructuredTool

from tools.fee_tools import check_fee_status
from tools.policy_tools import search_academic_information, search_policy
from tools.scholarship_tools import check_scholarship_status
from tools.student_tools import get_student_profile
from tools.support_tools import create_support_ticket

_FUNCTIONS = [get_student_profile, check_fee_status, check_scholarship_status, create_support_ticket,
              search_academic_information, search_policy]


def get_tools() -> list[StructuredTool]:
    return [StructuredTool.from_function(f, name=f.__name__, description=f.__doc__) for f in _FUNCTIONS]


def get_tool_map() -> dict[str, StructuredTool]:
    return {t.name: t for t in get_tools()}
