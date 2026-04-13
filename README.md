# LLM Test Data Factory

面向 **LLM 应用 / Agent / RAG** 场景的离线测试数据工厂：用 **LangGraph（StateGraph）** 将「主题规划 → 知识语料 → QA 合成 → 审核 → 修订/接受 → 导出」编排成可讲解、可运行的轻量流水线。

## 为什么要做这个项目

当你优化 Paper-Agent 的 RAG（解析、query 增强、检索、重排、上下文组织等）时，如果没有**稳定、可复现、可对比**的测试集，很容易出现「感觉变好但无法客观证明」的问题。  
本项目用于**批量制造结构化测试数据**，导出：

- `knowledge.jsonl`：向量库检索语料
- `dataset_full.jsonl`：带元数据的完整样本（接受/拒绝/待处理）
- `dataset_eval.csv`：仅 `query,answer`，便于直接评测

## 核心流程

1. `plan_topics`：根据 domain 规划 8~10 个主题桶（子主题 + 配额）
2. `generate_knowledge`：可选先拉取外部网页摘要（DuckDuckGo / Tavily），再按当前主题批次生成 5~10 条知识（120~260 字量级），`knowledge.jsonl` 可带 `sources` 溯源 URL
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
│     ├─ similarity.py
│     ├─ rate_limiter.py
│     └─ web_search.py
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

## 环境变量（硅基流动 SiliconFlow）

**在哪里填入 API Key（任选其一，推荐第 1 种）：**

1. **项目根目录 `.env` 文件（推荐）**  
   在 `LLM Test Data Factory/` 下新建或编辑 `.env`，至少包含 Key；**模型名建议在 `.env` 中显式配置**（与硅基流动模型广场 ID 一致）：
   ```env
   SILICONFLOW_API_KEY="sk-你的硅基流动密钥"
   SILICONFLOW_MODEL="Qwen/Qwen3.5-35B-A3B"
   ```
   `app/main.py` 已调用 `load_dotenv()`，运行 `python app/main.py` 时会自动加载。

2. **系统 / 终端环境变量**  
   Windows PowerShell 示例：
   ```powershell
   $env:SILICONFLOW_API_KEY="sk-..."
   python app/main.py
   ```

| 变量 | 说明 | 默认值 |
|---|---|---|
| `FACTORY_DOMAIN` | **生成领域/主题方向**（一段话）；不设置则用内置默认领域 | 见 `app/config.py` |
| `SILICONFLOW_API_KEY` | **硅基流动 API Key（sk-...），优先读取** | 空（运行前必填其一） |
| `OPENAI_API_KEY` | 未设置上一项时的兼容回退 | 空 |
| `OPENAI_BASE_URL` | OpenAI 兼容 Base URL | `https://api.siliconflow.cn/v1` |
| `SILICONFLOW_MODEL` | **模型 ID（推荐在 `.env` 配置）**，须与模型广场一致 | 未设置时为 `Qwen/Qwen3.5-35B-A3B` |
| `OPENAI_MODEL` | 兼容命名；仅当未设置 `SILICONFLOW_MODEL` 时生效 | 同上默认 |
| `LLM_MAX_RETRIES` | LLM 重试次数 | `3` |
| `LLM_TIMEOUT_SEC` | 超时秒数 | `120` |
| `SILICONFLOW_RATE_LIMIT_ENABLED` | 是否启用客户端 RPM/TPM 限流 | `true` |
| `SILICONFLOW_RPM_LIMIT` | 滑动 60 秒内最多请求次数（与控制台 RPM 对齐） | `1000` |
| `SILICONFLOW_TPM_LIMIT` | 滑动 60 秒内最多 token 数（与控制台 TPM 对齐） | `80000` |
| `SILICONFLOW_TPM_OUTPUT_RESERVE` | 每次请求前为「尚未返回的 completion」预留的 TPM 预算，偏小可能顶穿 TPM | `12000` |
| `WEB_SEARCH_ENABLED` | 是否在 `generate_knowledge` 前拉取外部检索摘要 | `true` |
| `WEB_SEARCH_BACKEND` | `duckduckgo`（免 Key）或 `tavily`（需 Key） | `duckduckgo` |
| `TAVILY_API_KEY` | Tavily 密钥；仅 `WEB_SEARCH_BACKEND=tavily` 时必填 | 空 |
| `WEB_SEARCH_MAX_RESULTS` | 每条 query 最多保留几条摘要 | `8` |
| `WEB_SEARCH_SNIPPET_CHARS` | 单条摘要最大字符数 | `500` |
| `WEB_SEARCH_HTTP_TIMEOUT_SEC` | 检索 HTTP 超时（秒） | `25` |
| `WEB_SEARCH_FALLBACK_DUCKDUCKGO` | Tavily 失败/无结果时是否回退 DuckDuckGo | `true` |

换模型时修改 `.env` 中的 `SILICONFLOW_MODEL`（或设置 `OPENAI_MODEL`）即可，例如：`SILICONFLOW_MODEL="deepseek-ai/DeepSeek-V3"`。

**限流说明：**`app/utils/llm.py` 在每次 API 调用前通过 `app/utils/rate_limiter.py` 做**单进程内**滑动窗口控制（最近 60 秒）：先满足 RPM 与「预估 prompt + 预留 completion」的 TPM，再发起请求；成功时优先用响应里的 `usage` 计入 TPM，失败时保守按输入粗估计入。若你观察到仍偶发 429，可适当**增大** `SILICONFLOW_TPM_OUTPUT_RESERVE` 或略**降低** `SILICONFLOW_TPM_LIMIT` / `SILICONFLOW_RPM_LIMIT` 留余量。

### 外部网页检索（实时摘要）

为缓解「知识全靠模型记忆、缺少可核对时效信息」的问题，`generate_knowledge` 会在调用大模型前通过 `app/utils/web_search.py` 拉取一小批网页摘要，并注入 `app/prompts/generate_knowledge.txt` 的 `SEARCH_RESULTS` 段落；模型若引用检索要点，会在该条 `KnowledgeItem` 上写入 `sources`（仅允许为本轮检索结果中出现过的 URL，代码侧也会过滤）。

- **默认**：`WEB_SEARCH_BACKEND=duckduckgo`，依赖 `duckduckgo-search`，一般无需额外 Key；若网络环境不可用，可设 `WEB_SEARCH_ENABLED=false` 关闭。
- **更高质量**：申请 [Tavily](https://tavily.com/) 后在 `.env` 设置 `TAVILY_API_KEY` 与 `WEB_SEARCH_BACKEND=tavily`；失败时可自动回退 DuckDuckGo（`WEB_SEARCH_FALLBACK_DUCKDUCKGO=true`）。

### 如何指定生成主题（领域）

数据工厂**不**在代码里写死一组固定「主题列表」，而是用 **`domain`（领域描述）** 交给 `plan_topics` 节点，由模型产出 8~10 个 `TopicPlan`（每个含 `topic`、若干 `subtopics`、配额）。后续 `generate_knowledge` 按轮询主题桶写知识，`generate_qa` 优先抽样与当前轮转主题一致的知识再生成 QA。

你可以用下面任一方式指定「围绕什么生成」：

| 方式 | 做法 |
|---|---|
| **`.env`（推荐）** | 设置 `FACTORY_DOMAIN`，写一段中文（或中英）说明希望覆盖的技术方向、业务场景、受众与边界；保存后运行 `python app/main.py`。 |
| **改代码** | 编辑 `app/main.py` 里 `new_factory_state(domain=...)`，传入你自己的字符串；或改 `app/config.py` 中的 `_BUILTIN_DOMAIN` 作为项目默认。 |
| **高级：手写主题规划** | 若初始 `FactoryState` 里已带非空的 `topic_plans`，`plan_topics` 会**跳过** LLM 规划。可在 `main.py` 里构造 `topic_plans=[TopicPlan(...), ...]` 再 `invoke`（需与 `state.TopicPlan` 字段一致）。 |

`.env` 示例：

```env
FACTORY_DOMAIN="围绕医疗多模态 RAG：影像报告结构化、HIPAA 合规检索、临床术语归一化与评测指标；不要生成具体患者隐私。"
```

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
