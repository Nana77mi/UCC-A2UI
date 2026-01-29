from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..library.whitelist import EVENT_WHITELIST, LibraryWhitelist
from .templates import (
    render_common_errors,
    render_events_section,
    render_example_ir,
    render_header,
    render_intro,
    render_props_section,
)

CATEGORY_BUCKETS = ["Layout", "Style", "Data", "Behavior", "State", "Advanced", "Events", "Unknown/General"]


def _normalize_category(raw: str) -> str:
    raw_lower = (raw or "").strip().lower()
    for bucket in CATEGORY_BUCKETS:
        if bucket.lower().startswith(raw_lower) or raw_lower in bucket.lower():
            return bucket
    return "Unknown/General"


def _build_props(component) -> Dict[str, List[str]]:
    categories = {bucket: [] for bucket in CATEGORY_BUCKETS}
    if component.strict_params:
        for param in component.strict_params:
            category = _normalize_category(param.category)
            name = param.name.strip() if param.name else ""
            if name:
                categories[category].append(name)
    else:
        for key in component.key_params:
            categories["Unknown/General"].append(key)
    return categories


def generate_docs(output_dir: str | Path, whitelist: LibraryWhitelist) -> List[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for component in whitelist.components.values():
        categories = _build_props(component)
        sample_prop = component.key_params[0] if component.key_params else None
        content = "\n\n".join(
            [
                render_header(component.component_type, component.name_cn),
                render_intro(component.name_cn),
                render_props_section(categories),
                render_events_section(EVENT_WHITELIST),
                render_example_ir(component.component_type, sample_prop),
                render_common_errors(),
            ]
        ).strip() + "\n"
        path = output_dir / f"{component.component_type}.md"
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
