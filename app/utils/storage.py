import json
import os
from pathlib import Path
from pydantic import BaseModel

OUTPUT_DIR = Path("data/outputs")


def save_json(model: BaseModel, filename: str) -> None:
    """Saves any Pydantic model as pretty JSON under data/outputs/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    print(f"[storage] Saved {filename}")


def load_json(model_class, filename: str):
    """Loads and validates a JSON file back into the given Pydantic model class.
    Returns None if the file doesn't exist yet."""
    path = OUTPUT_DIR / filename
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return model_class.model_validate(data)
