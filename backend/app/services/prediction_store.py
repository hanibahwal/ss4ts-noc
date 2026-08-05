from datetime import datetime

from app.database import SessionLocal

from app.models.network_prediction import (
    NetworkPrediction,
)


def save_prediction(
    *,
    device_ip: str,
    risk_score: float,
    confidence: float,
    risk_level: str,
    issue_type: str,
    reason: str,
):

    db = SessionLocal()

    try:

        prediction = NetworkPrediction(
            device_ip=device_ip,
            prediction_time=datetime.utcnow(),
            risk_score=risk_score,
            confidence=confidence,
            risk_level=risk_level,
            issue_type=issue_type,
            reason=reason,
        )

        db.add(prediction)

        db.commit()

        db.refresh(prediction)

        return prediction

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()
