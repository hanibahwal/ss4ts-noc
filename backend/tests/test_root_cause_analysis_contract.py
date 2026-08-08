from app.models.root_cause_analysis import (
    RootCauseAnalysisResult,
    RootCauseFinding,
)


def test_root_cause_analysis_contract():
    finding = RootCauseFinding(
        code="HIGH_CPU",
        severity="critical",
        title="High CPU usage",
        evidence={"cpu": 95},
        recommendation="Review device load",
    )

    result = RootCauseAnalysisResult(
        status="completed",
        root_causes=[finding],
        confidence=0.95,
        summary="CPU issue detected",
    )

    assert result.status == "completed"
    assert result.confidence == 0.95
    assert len(result.root_causes) == 1
    assert result.root_causes[0].code == "HIGH_CPU"
