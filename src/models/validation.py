from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    passed: bool
    checks: dict
    route_to: str
    human_review_reason: Optional[str] = None
