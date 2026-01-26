from __future__ import annotations

import json
from pathlib import Path

from ucc_a2ui.config import Config
from ucc_a2ui.generator import generate_ui
from ucc_a2ui.library import LibrarySourceConfig, build_whitelist, load_library_sources


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config.yaml"
    config = Config.load(config_path)

    source_format = config.get("library", "source_format", default="json")
    component_path = config.get("library", "component_path")
    params_path = config.get("library", "params_path")

    sources = LibrarySourceConfig(
        component_path=str(repo_root / component_path),
        params_path=str(repo_root / params_path),
        source_format=source_format,
    )
    components, params = load_library_sources(sources)
    whitelist = build_whitelist(components, params)

    out_dir = repo_root / "out"
    prompt = "创建一个包含按钮与文本的页面"
    ir, report = generate_ui(prompt, config, whitelist, out_dir, print_messages=True, save_plan=True)

    print("\n[debug] ui_ir.json")
    print(json.dumps(ir, ensure_ascii=False, indent=2))
    print("\n[debug] ui_report.json")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
