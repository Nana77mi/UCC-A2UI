from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..config import Config
from ..library.theme import merge_theme_tokens
from ..library.whitelist import LibraryWhitelist
from .json_extract import JSONExtractError, extract_first_json
from .llm_client_base import LLMClientBase
from .llm_dashscope_qwen import DashScopeQwenLLM
from .llm_mock import MockLLM
from .llm_openai_compat import OpenAICompatibleLLM
from .prompt_builder import build_prompt_messages
from .validator import validate_ir


def build_llm(config: Dict[str, Any], whitelist: LibraryWhitelist) -> LLMClientBase:
    mode = config.get("mode", "mock")
    if mode == "openai_compatible":
        return OpenAICompatibleLLM(
            base_url=config.get("base_url", ""),
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
            temperature=float(config.get("temperature", 0.2)),
            max_tokens=int(config.get("max_tokens", 2000)),
            timeout_s=int(config.get("timeout_s", 60)),
        )
    if mode == "dashscope_qwen":
        return DashScopeQwenLLM(
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
            temperature=float(config.get("temperature", 0.2)),
            max_tokens=int(config.get("max_tokens", 2000)),
            timeout_s=int(config.get("timeout_s", 60)),
        )
    return MockLLM(whitelist)


def generate_ui(
    prompt: str,
    config: Config,
    whitelist: LibraryWhitelist,
    out_dir: str | Path,
    print_messages: bool = False,
    save_plan: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    defaults = {
        "width": config.get("generator", "default_width", default=1366),
        "height": config.get("generator", "default_height", default=768),
        "layout": config.get("generator", "default_layout", default="vertical"),
        "gap": config.get("generator", "default_gap", default=12),
        "padding": config.get("generator", "default_padding", default=16),
    }
    theme = merge_theme_tokens(whitelist.theme_tokens)
    messages = build_prompt_messages(prompt, whitelist, theme, defaults)
    if print_messages:
        for message in messages:
            print(f"[{message['role']}]\n{message['content']}\n")

    llm_config = config.get_resolved("llm", default={})
    llm = build_llm(llm_config, whitelist)
    response = llm.complete(messages)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.txt"

    try:
        data = extract_first_json(response.content)
    except JSONExtractError:
        raw_path.write_text(response.content, encoding="utf-8")
        report = {
            "SchemaPass": False,
            "ComponentWhitelistPass": False,
            "PropsWhitelistPass": False,
            "EventsWhitelistPass": False,
            "BindingSanity": False,
            "ThemePass": False,
            "errors": [{"code": "E_JSON_PARSE", "path": "$", "message": "Failed to parse JSON"}],
        }
        (out_dir / "ui_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return {}, report

    plan = data.get("plan") if isinstance(data, dict) else None
    ir = data.get("ir") if isinstance(data, dict) else data
    if ir is None:
        raw_path.write_text(response.content, encoding="utf-8")
        report = {
            "SchemaPass": False,
            "ComponentWhitelistPass": False,
            "PropsWhitelistPass": False,
            "EventsWhitelistPass": False,
            "BindingSanity": False,
            "ThemePass": False,
            "errors": [{"code": "E_NULL_IR", "path": "$.ir", "message": "LLM returned null IR"}],
        }
        (out_dir / "ui_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {}, report

    if save_plan and plan is not None:
        (out_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    (out_dir / "ui_ir.json").write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")

    strict = bool(config.get("library", "strict_params", default=False))
    report = validate_ir(ir, whitelist, strict=strict)
    (out_dir / "ui_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return ir, report
