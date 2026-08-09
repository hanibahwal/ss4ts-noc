from __future__ import annotations

import os
from pathlib import Path


DEFAULT_DATA_DIRECTORY = Path("./data")


def get_data_directory() -> Path:
    configured = os.getenv(
        "SS4TS_DATA_DIR",
        str(DEFAULT_DATA_DIRECTORY),
    ).strip()

    if not configured:
        raise RuntimeError(
            "SS4TS_DATA_DIR must not be empty"
        )

    return Path(configured)


def data_path(
    filename: str,
) -> Path:
    normalized = str(filename).strip()

    if not normalized:
        raise ValueError(
            "Persistent data filename must not be empty"
        )

    if Path(normalized).name != normalized:
        raise ValueError(
            "Persistent data filename must not contain directories"
        )

    return get_data_directory() / normalized
