from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator


class FraudVerdict(BaseModel):
    verdict: Literal['fraud', 'suspicious', 'safe']
    confidence: float
    matched_patterns: List[str]
    message_signals: List[str]
    url_signals: List[str]
    plain_summary: str
    domain_age_days: Optional[int] = None

    @field_validator('confidence')
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))
