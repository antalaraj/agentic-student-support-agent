"""Authenticated user models and context representations."""
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class AuthUser:
    """Immutable representation of an authenticated user session."""
    user_id: str
    username: str
    role: str                       # 'student' or 'admin'
    student_id: Optional[str]       # None for admins
    full_name: str
    email: str
    is_active: bool = True

    def is_admin(self) -> bool:
        return self.role.lower() == "admin"

    def is_student(self) -> bool:
        return self.role.lower() == "student"

    def to_dict(self) -> dict:
        return asdict(self)
