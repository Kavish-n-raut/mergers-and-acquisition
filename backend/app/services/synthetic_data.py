from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SyntheticDataError(ValueError):
    pass


SYNTHETIC_DIR = Path("runtime_artifacts") / "synthetic"


def load_synthetic_dataset(name: str) -> dict[str, Any]:
    allowed = {"vdr_sample", "negotiation_sample", "pmi_sample"}
    if name not in allowed:
        raise SyntheticDataError(f"Unsupported synthetic dataset '{name}'.")

    path = SYNTHETIC_DIR / f"{name}.json"
    if not path.exists():
        raise SyntheticDataError(f"Synthetic dataset file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
    except json.JSONDecodeError as exc:
        raise SyntheticDataError(f"Invalid JSON in synthetic dataset '{name}': {exc}") from exc


def list_synthetic_datasets() -> list[str]:
    return ["vdr_sample", "negotiation_sample", "pmi_sample"]

