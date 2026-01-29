# UCC A2UI（方案 A）UI 生成系统

本仓库从零实现 **A2UI 方案 A（UCC IR 为主 + 测试集/评测集）** 的同款格式和闭环，只允许使用 UCC 白名单组件与参数体系。所有组件、参数、主题色均来自 JSON 真源，并且支持组件文档自动生成与 embedding 索引同步更新。

## 方案 A 对齐说明
- **层 1：Library（SSOT）**：从 JSON 读取 UCC 组件清单与参数，生成 `library.json` 作为唯一真源输出。
- **层 2：Generator（NL -> UI IR）**：Prompt Builder（Plan + IR）、LLM 输出 JSON、IR 校验（Schema + 白名单 + binding/事件）并输出 `ui_ir.json` + `ui_report.json`。
- **层 3：Knowledge（Docs + Embedding）**：从 Library 生成组件文档，自动构建 embedding 索引，提供检索 CLI。
- **测试集/评测**：内置 fixtures + pytest 保障 prompt/规则变更可回归。

> 说明：本仓库不是直接拷贝 A2UI 实现，而是 **对齐 A2UI 方案 A 的结构、输出格式、数据流**，并将组件体系严格替换为 UCC 白名单。当前只支持 JSON 真源。

---

## 快速开始（mock 模式离线）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# 同步：读取 JSON schema -> library.json -> docs -> index
ucc-a2ui sync --config config.yaml

# 生成：自然语言 -> IR + report
ucc-a2ui generate --prompt "创建一个包含按钮与文本的页面" --out out/

# 校验
ucc-a2ui validate --in out/ui_ir.json

# 检索
ucc-a2ui search --query "按钮" --k 5
```

> mock 模式默认离线可运行。默认使用 `data/ucc_component_params.json` 作为输入。可在 `config.yaml` 中覆盖路径。

---

## PyCharm 一键调试（无需 CLI）

项目提供 `scripts/debug_run.py` 直接运行入口，适合在 PyCharm 里点运行：

```bash
python scripts/debug_run.py
```

该脚本会读取 `config.yaml`，加载 JSON 白名单，运行 `generate` 并输出 IR/Report 与 Plan。

---

## JSON 真源格式

### `data/ucc_component_params.json`
```json
{
  "schema_version": "ucc-component-params@v0",
  "source": {
    "file": "UCC_Component_Params_v0.xlsx",
    "sheet": "UCC_Component_Params_v0"
  },
  "components": [
    {
      "type": "button",
      "group": "基础组件",
      "component_name": "Button",
      "props_by_category": {
        "Data": [
          {
            "name": "text",
            "type": "string",
            "enum": [],
            "description": "按钮文本",
            "default": null,
            "required": true,
            "notes": ""
          }
        ]
      }
    }
  ]
}
```

---

## Ollama 模式配置（LLM + Embeddings）

`config.yaml` 示例：
```yaml
llm:
  mode: openai_compatible
  base_url: http://localhost:11434/v1
  api_key: ENV:OPENAI_API_KEY
  model: qwen2.5-7b-instruct
  temperature: 0.2
  max_tokens: 2000
  timeout_s: 60

embed:
  mode: openai_compatible
  base_url: http://localhost:11434/v1
  api_key: ENV:OPENAI_API_KEY
  model: bge-large-zh
  index_dir: index/ucc_docs
  batch_size: 64
```

---

## Qwen 模式配置

### OpenAI-compatible
```yaml
llm:
  mode: openai_compatible
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  api_key: ENV:DASHSCOPE_API_KEY
  model: qwen2.5-7b-instruct
```

### DashScope 官方
```yaml
llm:
  mode: dashscope_qwen
  api_key: ENV:DASHSCOPE_API_KEY
  model: qwen2.5-7b-instruct
```

> embeddings 可用 `openai_compatible` 或 `dashscope_qwen`，否则自动退化为 mock embedding。

---

## 新增组件流程
1. 更新 JSON（组件/参数）。
2. 执行 `ucc-a2ui sync`：
   - 自动生成/更新 `library.json`
   - 重新生成 `docs/components/*.md`
   - 增量更新 `index/*`（仅新组件时追加，组件变更/删除会触发重建）
3. `generate` 立即支持新组件（白名单更新）。

---

## 输出示例

### IR（`out/ui_ir.json`）
```json
{
  "version": "ucc-ui-ir@v0",
  "theme": {},
  "variables": [],
  "tree": {
    "type": "button",
    "props": {"text": "示例"},
    "events": {},
    "children": []
  }
}
```

### Report（`out/ui_report.json`）
```json
{
  "SchemaPass": true,
  "ComponentWhitelistPass": true,
  "PropsWhitelistPass": true,
  "EventsWhitelistPass": true,
  "BindingSanity": true,
  "ThemePass": true,
  "errors": []
}
```

### Plan（`out/plan.json`）
```json
{
  "intent": "生成一个基础页面",
  "widgets": ["button"],
  "bindings": [],
  "events": [],
  "layout": "vertical"
}
```

---

## CLI 说明

```bash
ucc-a2ui sync --config config.yaml
ucc-a2ui generate --config config.yaml --prompt "..." --out out/ [--print-messages] [--save-plan]
ucc-a2ui validate --config config.yaml --in out/ui_ir.json
ucc-a2ui search --config config.yaml --query "..." --k 5
```

返回码：
- `generate`: 校验通过返回 0；校验失败返回 2；异常返回 1。
- `sync`: 成功返回 0；失败返回 1。

---

## 目录结构

```
ucc-a2ui/
  pyproject.toml
  config.yaml
  README.md
  data/
    ucc_component_params.json
  scripts/
    debug_run.py
  src/ucc_a2ui/
    __init__.py
    config.py
    library/
      __init__.py
      json_loader.py
      normalize.py
      whitelist.py
      theme.py
      export.py
    docs/
      __init__.py
      docgen.py
      templates.py
    embed/
      __init__.py
      embedder_base.py
      embedder_mock.py
      embedder_openai_compat.py
      embedder_dashscope_qwen.py
      index_faiss.py
      chunker.py
      search.py
    generator/
      __init__.py
      prompt_builder.py
      llm_client_base.py
      llm_mock.py
      llm_openai_compat.py
      llm_dashscope_qwen.py
      json_extract.py
      ir_schema.py
      validator.py
      generate.py
    cli.py
  tests/
    test_validator.py
    test_json_extract.py
    test_sync_docgen_mock_embed.py
    test_generate_mock.py
    fixtures/ui_prompts.jsonl
```

---

## 设计要点（摘要）
- **白名单约束**：组件 type 只来自 JSON schema 的 `type` 字段，统一 normalize 为 `lower_snake`；props 仅允许 `props_by_category` 中出现的字段。校验器强制检查，生成器的 Prompt 也注入白名单摘要。
- **文档 & embedding 同步**：`ucc-a2ui sync` 串联 Library -> docs -> FAISS index，新增组件后立即更新 docs/index 并可检索。
- **严格参数模式**：`config.yaml` 中 `library.strict_params: true` 时，prop 白名单切换为 Params_v0 的 ParamName，并按 ParamCategory 分类。
