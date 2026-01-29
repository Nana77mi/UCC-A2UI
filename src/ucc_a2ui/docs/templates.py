from __future__ import annotations

from typing import Dict, List


def render_header(component_type: str, name_cn: str) -> str:
    return f"# {component_type}\n\n**中文名**：{name_cn or '未提供'}\n"


def render_intro(name_cn: str) -> str:
    desc = name_cn or "未提供"
    return f"## 组件简介\n\n该组件中文名为 **{desc}**，用于构建 UCC UI 方案中的对应控件。\n"


def render_props_section(categories: Dict[str, List[str]]) -> str:
    lines = ["## Allowed Props\n"]
    for category, props in categories.items():
        if not props:
            continue
        lines.append(f"### {category}\n")
        for prop in props:
            lines.append(f"- `{prop}`")
        lines.append("")
    return "\n".join(lines)


def render_events_section(events: List[str]) -> str:
    lines = ["## Events\n"]
    lines.append("支持的事件：")
    for event in events:
        lines.append(f"- `{event}`")
    lines.append("")
    return "\n".join(lines)


def render_example_ir(component_type: str, sample_prop: str | None = None) -> str:
    prop_line = f'    "{sample_prop}": "示例"' if sample_prop else ""
    return (
        "## 示例 IR JSON\n\n"
        "```json\n"
        "{\n"
        "  \"version\": \"ucc-ui-ir@v0\",\n"
        "  \"theme\": {},\n"
        "  \"variables\": [],\n"
        "  \"tree\": {\n"
        f"    \"type\": \"{component_type}\",\n"
        "    \"props\": {\n"
        f"{prop_line}\n"
        "    },\n"
        "    \"events\": {},\n"
        "    \"children\": []\n"
        "  }\n"
        "}\n"
        "```\n"
    )


def render_common_errors() -> str:
    return (
        "## 常见错误\n\n"
        "- 使用未在白名单中的 prop 或组件类型。\n"
        "- 绑定变量不存在（如 `textBinding` 引用了未定义变量）。\n"
        "- 事件名称不在允许事件列表中。\n"
    )
