# LLM Test Data Factory

面向 **LLM 应用 / Agent / RAG** 场景的离线测试数据工厂：用 **LangGraph（StateGraph）** 将「主题规划 → 知识语料 → QA 合成 → 审核 → 修订/接受 → 导出」编排成可讲解、可运行的轻量流水线。

## 为什么要做这个项目

当你优化 Paper-Agent 的 RAG（解析、query 增强、检索、重排、上下文组织等）时，如果没有**稳定、可复现、可对比**的测试集，很容易出现「感觉变好但无法客观证明」的问题。  
本项目用于**批量制造结构化测试数据**，导出：

- `knowledge.jsonl`：向量库检索语料
- `dataset_full.jsonl`：带元数据的完整样本（接受/拒绝/待处理）
- `dataset_eval.csv`：仅 `query,answer`，便于直接评测

## 核心流程（文字版）

1. `plan_topics`：根据 domain 规划 8~10 个主题桶（子主题 + 配额）
2. `generate_knowledge`：按当前主题批次生成 5~10 条知识（120~260 字量级）
3. `generate_qa`：基于抽样知识生成约 5 条 QA，并绑定 `evidence_kids`
4. `review_qa`：审核歧义、证据支撑、可判分性、近重复等
5. `revise_or_accept`：接受入库；不合格最多修订 `max_revision_rounds` 次（默认 2）
6. 满足终止条件后 `export_dataset` 写出三类文件并结束

终止条件（满足任一）：

- `len(accepted_qa) >= target_qa_count`（默认 200）
- 或 `sum(len(content)) >= target_knowledge_chars`（默认 12000）

## 目录结构

```
LLM Test Data Factory/
├─ app/
│  ├─ main.py
│  ├─ graph.py
│  ├─ state.py
│  ├─ config.py
│  ├─ nodes/
│  │  ├─ plan_topics.py
│  │  ├─ generate_knowledge.py
│  │  ├─ generate_qa.py
│  │  ├─ review_qa.py
│  │  ├─ revise_or_accept.py
│  │  └─ export_dataset.py
│  ├─ prompts/
│  │  ├─ plan_topics.txt
│  │  ├─ generate_knowledge.txt
│  │  ├─ generate_qa.txt
│  │  ├─ review_qa.txt
│  │  └─ revise_qa.txt
│  └─ utils/
│     ├─ llm.py
│     ├─ json_parser.py
│     ├─ csv_export.py
│     └─ similarity.py
├─ outputs/
├─ README.md
└─ requirements.txt
```

## 安装

建议使用虚拟环境：

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI 或兼容服务的 API Key | 空（必填） |
| `OPENAI_BASE_URL` | 兼容接口 Base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名 | `gpt-4o-mini` |
| `LLM_MAX_RETRIES` | LLM 重试次数 | `3` |
| `LLM_TIMEOUT_SEC` | 超时秒数 | `120` |

也可在项目根目录放置 `.env`（`python-dotenv` 会自动加载）。

## 运行

在项目根目录执行：

```bash
python app/main.py
```

运行结束后，默认导出到 `outputs/`：

- `knowledge.jsonl`
- `dataset_full.jsonl`
- `dataset_eval.csv`

## 输出文件说明

- **knowledge.jsonl**：每行一个 `KnowledgeItem` JSON，用于构建向量索引与检索评测语料池。
- **dataset_full.jsonl**：每行一个 `QASample` JSON（包含审核/修订元数据），适合审计与错误分析。
- **dataset_eval.csv**：标准 CSV，表头固定为 `query,answer`，仅包含**已接受**样本，便于接入你的评测脚本或后续 LangSmith 实验。

## 可扩展点（保持克制的建议）

- 将 `LLMClient` 替换为本地模型或网关（仍建议保留 JSON 约束与解析保护）
- 在 `review_qa` 增加规则层（正则/关键词）与模型层组合
- 增加 `langsmith` trace：在节点入口打点（不引入复杂微服务）
- 将 `target_*` 与 domain 改为 CLI 参数（当前集中在 `config.py` / `main.py`）

## 如何用于后续 RAG 对比实验

1. 固定一份 `knowledge.jsonl` 与 `dataset_eval.csv` 作为**基准快照**（文件名加日期版本即可）
2. 构建向量库时仅使用 `knowledge.jsonl`（或从中抽样子集做消融）
3. 对同一 `dataset_eval.csv` 在优化前后分别跑检索+生成流水线，统计命中率、引用一致性、延迟与成本
4. 用 `dataset_full.jsonl` 定位「证据不足 / 歧义 / 重复」等系统性问题，反哺 prompt 与解析策略

## 备注

- 本项目定位为**离线批处理**与**面试展示**：强调图编排、状态机、数据治理，而非企业级平台能力。
- 若模型输出偶发非 JSON，解析器会尽量清洗；节点内也会捕获异常，避免单条样本拖垮全流程。
