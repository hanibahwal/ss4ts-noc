from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RootCauseFinding:
    code: str
    severity: str
    title: str
    evidence: dict[str, Any]
    recommendation: str


@dataclass
class RootCauseAnalysisResult:
    status: str
    root_causes: list[RootCauseFinding]
    confidence: float
    summary: str
