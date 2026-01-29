from __future__ import annotations

from typing import Any, Dict, List

from ..library.whitelist import EVENT_WHITELIST, LibraryWhitelist


def build_library_summary(whitelist: LibraryWhitelist, limit: int = 20) -> str:
    lines = ["组件白名单摘要："]
    for component in list(whitelist.components.values())[:limit]:
        key_params = ", ".join(component.key_params[:8])
        lines.append(f"- {component.component_type} ({component.name_cn}) | KeyParams: {key_params}")
    return "\n".join(lines)


def build_prompt_messages(
    prompt: str,
    whitelist: LibraryWhitelist,
    theme_tokens: Dict[str, str],
    defaults: Dict[str, Any],
) -> List[Dict[str, str]]:
    system_message = (
        "你是 A2UI 方案 A 的 UI IR 生成器。只能使用白名单组件与 props。"
        "输出必须是 JSON，并且包含 Plan JSON 与最终 IR JSON。"
        "节点必须包含 type/props/events/children 字段。"
        "事件只能来自允许事件列表。"
    )
    context_message = (
        f"{build_library_summary(whitelist)}\n"
        f"允许事件：{', '.join(EVENT_WHITELIST)}\n"
        f"默认主题 tokens：{theme_tokens}\n"
    )
    user_message = (
        f"用户需求：{prompt}\n"
        "默认页面信息："
        f"width={defaults['width']}, height={defaults['height']}, "
        f"root layout={defaults['layout']}, gap={defaults['gap']}, padding={defaults['padding']}。"
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "context", "content": context_message},
        {"role": "user", "content": user_message},
    ]
