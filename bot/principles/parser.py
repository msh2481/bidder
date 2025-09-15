import re
from dataclasses import dataclass


@dataclass
class PrincipleItem:
    path: list[
        str
    ]  # e.g., ["General principles", "Self-improvement", "5-step process"]
    text: str  # leaf text (multiline allowed)


_heading_re = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_principles(md_text: str) -> list[PrincipleItem]:
    """
    Turn a Markdown-like outline into leaf content items.
    Each item corresponds to a block of text that follows the *current* deepest heading
    until the next heading (or EOF). The item's `path` is the full breadcrumb (H1..H6)
    leading to that block.
    """
    lines = md_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    current_path: list[str] = []  # dynamic path by heading levels
    buffer_lines: list[str] = []  # accumulating content lines for current path
    buffer_path: list[str] | None = None
    items: list[PrincipleItem] = []

    def flush():
        nonlocal buffer_lines, buffer_path, items
        # Create an item if there's non-empty content
        if any(l.strip() for l in buffer_lines):
            text = "\n".join(buffer_lines).strip()
            path = [p for p in (buffer_path or current_path) if p]
            items.append(PrincipleItem(path=path, text=text))
        buffer_lines = []

    for line in lines:
        m = _heading_re.match(line)
        if m:
            # New heading -> previous textual block belongs to prior path
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()

            # Ensure current_path length
            if len(current_path) < level:
                current_path += [""] * (level - len(current_path))
            # Truncate deeper levels, set this level's title
            current_path = current_path[:level]
            current_path[level - 1] = title
            # Next text will be attached to this path
            buffer_path = current_path.copy()
        else:
            buffer_lines.append(line)

    # Final flush
    flush()
    # Keep only items that have at least one heading in the path and non-empty text
    items = [it for it in items if it.path and it.text.strip()]
    return items
