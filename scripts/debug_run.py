from __future__ import annotations

import json
from pathlib import Path

from ucc_a2ui.config import Config
from ucc_a2ui.generator import generate_ui
from ucc_a2ui.library import build_whitelist, load_component_schema_json


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config.yaml"
    config = Config.load(config_path)

    component_path = config.get("library", "component_path")
    if not component_path:
        raise ValueError("library.component_path is required for JSON schema input.")

    components, _ = load_component_schema_json(repo_root / component_path)
    whitelist = build_whitelist(components)

    out_dir = repo_root / "out"
    prompt = "创建一个包含按钮与文本的页面"
    ir, report = generate_ui(prompt, config, whitelist, out_dir, print_messages=True, save_plan=True)

    print("\n[debug] ui_ir.json")
    print(json.dumps(ir, ensure_ascii=False, indent=2))
    print("\n[debug] ui_report.json")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
