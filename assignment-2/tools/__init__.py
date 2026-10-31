"""Tool registry for Assignment 2 (Safe and Production-Aware Student Support Agent).
Exposes the 6 domain tools plus the sensitive action tool 'request_fee_extension'.
"""
from langchain_core.tools import StructuredTool

from tools.approval_tools import request_fee_extension
from tools.fee_tools import check_fee_status
from tools.policy_tools import search_academic_information, search_policy
from tools.scholarship_tools import check_scholarship_status
from tools.student_tools import get_student_profile
from tools.support_tools import create_support_ticket

_FUNCTIONS = [
    get_student_profile,
    check_fee_status,
    check_scholarship_status,
    create_support_ticket,
    search_academic_information,
    search_policy,
    request_fee_extension,
]


def get_tools() -> list[StructuredTool]:
    """Return all available structured tools for the agent."""
    return [StructuredTool.from_function(f, name=f.__name__, description=f.__doc__) for f in _FUNCTIONS]


def get_tool_map() -> dict[str, StructuredTool]:
    """Return a lookup map of tool name to StructuredTool instance."""
    return {t.name: t for t in get_tools()}
