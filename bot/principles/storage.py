import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..common.config import DATA_DIR


@dataclass
class Principle:
    id: int
    category: str
    title: str
    text: str


def principles_file(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}_principles.json"


def time_file(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}_time.json"


def load_principles(user_id: int) -> list[Principle]:
    """Load user's principles from JSON file."""
    p = principles_file(user_id)
    if not p.exists():
        return []

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [Principle(**item) for item in data]
    except Exception:
        return []


def save_principles(user_id: int, principles: list[Principle]) -> None:
    """Save user's principles to JSON file."""
    p = principles_file(user_id)
    data = [asdict(principle) for principle in principles]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_principle(user_id: int, category: str, title: str, text: str) -> int:
    """Add a new principle and return its ID."""
    principles = load_principles(user_id)
    new_id = max([p.id for p in principles], default=0) + 1
    new_principle = Principle(id=new_id, category=category, title=title, text=text)
    principles.append(new_principle)
    save_principles(user_id, principles)
    return new_id


def remove_principle(user_id: int, principle_id: int) -> bool:
    """Remove a principle by ID. Returns True if found and removed."""
    principles = load_principles(user_id)
    original_count = len(principles)
    principles = [p for p in principles if p.id != principle_id]

    if len(principles) < original_count:
        save_principles(user_id, principles)
        return True
    return False


def get_principle(user_id: int, principle_id: int) -> Optional[Principle]:
    """Get a specific principle by ID."""
    principles = load_principles(user_id)
    for principle in principles:
        if principle.id == principle_id:
            return principle
    return None


# Legacy support for scheduler
def load_raw_principles(user_id: int) -> Optional[str]:
    """Convert individual principles to markdown format for scheduler compatibility."""
    principles = load_principles(user_id)
    if not principles:
        return None

    # Group by category
    categories = {}
    for principle in principles:
        if principle.category not in categories:
            categories[principle.category] = []
        categories[principle.category].append(principle)

    # Generate markdown
    lines = []
    for category, category_principles in categories.items():
        lines.append(f"# {category}")
        lines.append("")
        for principle in category_principles:
            lines.append(f"## {principle.title}")
            lines.append(principle.text)
            lines.append("")

    return "\n".join(lines)


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
