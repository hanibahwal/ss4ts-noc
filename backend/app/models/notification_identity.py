from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class NotificationIdentity:
    identity_id: str
    username: str
    role: str
    active: bool = True
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.identity_id:
            raise ValueError(
                "identity_id must not be empty"
            )

        if not self.username:
            raise ValueError(
                "username must not be empty"
            )

        if not self.role:
            raise ValueError(
                "role must not be empty"
            )

        if self.created_at is None:
            self.created_at = _utc_now()

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "username": self.username,
            "role": self.role,
            "active": self.active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
        }
