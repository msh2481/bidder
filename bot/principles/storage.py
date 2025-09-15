import json
from pathlib import Path
from typing import Optional

from ..common.config import DATA_DIR


def principles_file(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}.txt"


def time_file(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}_time.json"


def save_raw_principles(user_id: int, raw_text: str) -> None:
    principles_file(user_id).write_text(raw_text, encoding="utf-8")


def load_raw_principles(user_id: int) -> Optional[str]:
    p = principles_file(user_id)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def save_time_config(user_id: int, hhmm: str) -> None:
    from ..common.config import SERVER_TZINFO

    tf = time_file(user_id)
    config = {"time": hhmm, "tzname": str(SERVER_TZINFO)}
    tf.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_time_config(user_id: int) -> Optional[dict]:
    tf = time_file(user_id)
    if tf.exists():
        try:
            return json.loads(tf.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None
