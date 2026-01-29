# UCC A2UI 标准部署与使用流程

本文档给出从部署到使用的标准流程，适用于生产/预发/测试环境。

---

## 1. 部署前准备

### 1.1 组件 SSOT（JSON）
确保准备好统一 JSON schema（示例见 `data/ucc_component_params.json`）。部署时使用配置项 `library.component_path` 指向该文件。

### 1.2 运行环境
- Python >= 3.10
- 安装依赖（包含 LLM/Embedding 可选依赖）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

---

## 2. 配置

修改 `config.yaml`：
- `library.component_path` 指向 JSON schema
- `llm` 与 `embed` 根据环境切换：
  - mock（离线）
  - openai_compatible（Ollama / OpenAI-compatible）
  - dashscope_qwen（Qwen 官方）

---

## 3. 部署与初始化（同步）

首次部署或组件库更新后执行：

```bash
ucc-a2ui sync --config config.yaml
```

该命令会：
1. 生成 `library.json`
2. 生成 `docs/components/*.md`
3. 构建向量索引 `index/*`

---

## 4. 运行与使用

### 4.1 生成 UI IR

```bash
ucc-a2ui generate --prompt "创建一个包含按钮与文本的页面" --out out/
```

输出：
- `out/ui_ir.json`
- `out/ui_report.json`
- （可选）`out/plan.json`

### 4.2 校验

```bash
ucc-a2ui validate --in out/ui_ir.json
```

### 4.3 搜索（检索组件文档）

```bash
ucc-a2ui search --query "按钮" --k 5
```

---

## 5. IDE 调试

可直接运行：

```bash
python scripts/debug_run.py
```

该脚本会读取 `config.yaml` 并完成一次完整生成流程。

---

## 6. 生产推荐流程

1. 上游系统更新 JSON schema
2. 触发 `ucc-a2ui sync`
3. 服务调用 `generate`
4. 服务调用 `validate`
5. 校验通过后使用 `ui_ir.json`

---

## 7. 返回码

- `generate`：校验通过返回 0；校验失败返回 2；异常返回 1
- `sync`：成功返回 0；失败返回 1

