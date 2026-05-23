# 智能面试官 Agent —— 基于 LangChain 的多轮情境面试系统

**英文名：** Multi-Agent Job Interview Simulator with Automated Evaluation

模拟真实技术面试流程：Agent 根据**职位描述**与**候选人简历**动态提问、追问，结合**结构化评分**驱动状态机分支，并输出**结构化面试报告**。支持多会话隔离（Redis）、可 Docker 部署。

---

## 一句话亮点（简历 / 面试口述）

> 不是单次对话循环，而是 **状态机驱动的多轮面试**：动态追问、跑题检测、提前终止、多维度评分，并以 **FastAPI + Redis** 服务化落地，可对接招聘或实训平台。

---

## 实现状态总览

| 模块 | 状态 | 说明 |
|------|------|------|
| 模型层 · 出题 CoT + Self-Critique | ✅ | `InterviewQuestionComposer` |
| 模型层 · Prompt 实验 | ✅ | `prompt_strategy`: `zero_shot` / `few_shot` / `cot` |
| 模型层 · LLM 自动评回答 | ✅ | `AnswerEvaluationAgent`（`scorer`）；可传 `scores` 覆盖 |
| 模型层 · LLM 深度报告 | ✅ | `InterviewReportAgent`（`reporter`） |
| 多 Agent 编排 | ✅ | `InterviewAgentOrchestrator`：interviewer + scorer + reporter |
| 流式出题 SSE | ✅ | `POST /interview/start/stream` |
| Token 级可观测 | ✅ | `TokenUsageCallbackHandler` + `llm_token_usage` JSON 日志 |
| 可选 Celery 报告 | ✅ | `CELERY_BROKER_URL` + `interview_simulator.generate_llm_report` |
| 业务层 · 状态机 / 决策 / 记忆 | ✅ | `business_layer/*` |
| 工程层 ①②③ | ✅ | FastAPI、Redis、Docker、JSON 日志、健康探针 |

未设置 `JUDGE_API_KEY` 时自动回退 **HeuristicScorer**（中性分）与规则化报告。

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 动态出题 | 基于 JD + 简历，LangChain LCEL + CoT + Self-Critique 生成/改写问题 |
| 面试语言 | `interview_language`: `zh`（中文）/ `en`（英文），题目、追问、评分评语与报告随会话一致 |
| 追问与纠偏 | 低分追问、严重跑题换题、连续低分提前结束（规则 + FSM） |
| 结构化评估 | LLM 三轴 1–5（`AnswerEvaluationAgent`），或由 `scores` 字段覆盖 |
| 最终报告 | LLM 评估总结、优势、**可执行改进建议**、推荐学习主题 |
| 流式出题 | SSE：`POST /interview/start/stream` |
| Prompt 实验 | `zero_shot` / `few_shot` / `cot`（默认 `cot`） |
| 会话与并发 | `REDIS_URL` 外置会话；`acompose` / 线程池异步出题；多实例可共享 Redis |

---

## 架构分层

### 1. 模型能力层（Model Capability）

**已实现：**

1. 生成面试问题（`model_layer/chains.py` → `InterviewQuestionComposer`）  
2. 自检难度与 JD/简历相关性（`QuestionCritique`）  
3. 不足则自动改写问题（单次 rewrite）

**Prompt：** 当前主路径为 **CoT + Self-Critique**（`model_layer/prompts.py`）。Zero-shot / Few-shot 对比实验见 Roadmap。

**模型：** 默认智谱 **GLM**（`JUDGE_MODEL=glm-4`），经 `JUDGE_BASE_URL` OpenAI 兼容接口 + `langchain-openai` 调用。

**多 Agent（`model_layer/agents.py`）：**

| Agent | 类 | 职责 |
|-------|-----|------|
| Interviewer | `InterviewQuestionComposer` | 出题 + 自检 + 改写 |
| Scorer | `AnswerEvaluationAgent` | 回答三轴评分 + `key_facts` |
| Reporter | `InterviewReportAgent` | 面试结束深度报告 |

---

### 2. 业务逻辑层（Business Logic）

**① 面试状态机** ✅

状态：`initial` → `questioning` → `waiting_for_answer` → `evaluating` → `follow_up` | `next_question` → `finalize`。

`prompt_lane_for_state()` 映射 `question_chain` / `evaluation_chain` / `follow_up_chain` / `report_chain`；评分与报告已接对应 Agent。

**② 评分与决策模块** ✅

- 技术深度 / 表达清晰度 / 相关性：各 1–5（`RoundScores`）  
- 低分 → 追问（有上限）  
- 严重跑题（`relevance` 过低）→ 换题  
- 连续弱轮 → 提前 `finalize`（`EvaluationPolicy` 可配）

**③ 多轮记忆管理** ✅

`InterviewMemory`：滚动摘要、关键事实列表、最近对话尾部；`materialize_context_block()` 供后续 prompt 注入。

---

### 3. 落地工程层（Engineering）

| 组件 | 用途 |
|------|------|
| **Python** | 主语言 |
| **LangChain** | LCEL 出题链 |
| **FastAPI** | HTTP 服务与 OpenAPI |
| **Pydantic** | API 与会话、得分模型 |
| **Redis** | 可选会话持久化（`RedisSessionStore`） |
| **Docker** | `Dockerfile` + `docker-compose.yml` |

**工程 ① FastAPI 与 API 契约** ✅  
HTTP、`/interview/*`、`InMemorySessionStore`（无 `REDIS_URL` 时）。

**工程 ② Redis 与异步强化** ✅  
`SessionStore` 抽象、JSON 编解码、`acompose` / `asyncio.to_thread`、`BackgroundTasks` 审计。

**工程 ③ 可部署与可观测** ✅  
Docker Compose、JSON Lines 日志（`LOG_FORMAT=json`）、请求中间件、`/healthz` + `/readyz`、集成测试。

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/interview/start` | 创建会话；`prompt_strategy`、`evaluation_policy` |
| `POST` | `/interview/start/stream` | SSE 流式输出首题，结束时 `type: done` 含 `session_id` |
| `POST` | `/interview/ask` | 提交回答；省略 `scores` 时走 LLM 评分（`USE_LLM_SCORING`） |
| `GET` | `/interview/status/{id}` | 状态机快照 + 记忆；`report_ready` |
| `GET` | `/interview/report/{id}` | LLM 报告：评估、优势、改进建议、学习主题（未结束 409） |
| `GET` | `/healthz` | 存活探测 |
| `GET` | `/readyz` | 就绪探测（Redis 不可达时 503） |

交互示例见 `tests/test_integration.py`。

---

## 项目结构

```
src/interview_simulator/
├── model_layer/          # interviewer / scorer / reporter + 可观测 + SSE
├── business_layer/       # FSM、决策、记忆
└── engineering/          # FastAPI、Redis、Celery、日志、健康检查
tests/                    # 单元 / API / 集成（test_fakes 无需 API Key）
Dockerfile
docker-compose.yml
```

---

## 快速开始

### 环境变量

复制 `.env.example` 为 `.env` 后按需修改：

```bash
JUDGE_API_KEY=your_zhipu_api_key
JUDGE_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
JUDGE_MODEL=glm-4
USE_LLM_SCORING=true
USE_LLM_REPORT=true
# 不设 REDIS_URL → 单进程内存会话
# REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=86400
# CELERY_BROKER_URL=redis://localhost:6379/1   # 可选：后台预生成报告
LOG_FORMAT=text          # 或 json
LOG_LEVEL=INFO
```

### 安装与测试

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

### 本地启动 API

```bash
python -m pip install -e .
# Windows: set JUDGE_API_KEY=...
# Linux/macOS: export JUDGE_API_KEY=...
interview-api
# 或:
# python -m uvicorn interview_simulator.engineering.app:create_app --factory --host 0.0.0.0 --port 8000
```

OpenAPI：`http://127.0.0.1:8000/docs`

**Web 界面（推荐上手）：** 启动 API 后浏览器打开 `http://127.0.0.1:8000/` — 填写 JD / 简历、答题、查看评分与报告，无需手写 curl。

### Redis 会话（多实例）

```bash
export REDIS_URL=redis://localhost:6379/0
interview-api
```

`/healthz`：`backend` 为 `memory` 或 `redis`；`/readyz` 在 Redis 模式下要求 ping 成功。

### Docker

```bash
# 根目录 .env 至少包含 JUDGE_API_KEY
docker compose up --build
```

- API：`http://localhost:8000`  
- Redis：`localhost:6379`（容器内 `redis://redis:6379/0`）

### 可观测性

| 变量 | 说明 |
|------|------|
| `LOG_FORMAT` | `text`（默认）或 `json` / `jsonl` |
| `LOG_LEVEL` | `INFO`、`DEBUG` 等 |

Compose 默认 `LOG_FORMAT=json`。日志字段含 `request_id`、`duration_ms`、`audit_event`、`session_id` 等。

---

## 简历表述参考（可直接微调）

**项目名称：** 智能面试 Agent —— 基于 LangChain 的多轮情境面试系统  

**技术栈：** Python, LangChain, FastAPI, Redis, Docker, 智谱 GLM（OpenAI 兼容 API）

**核心贡献：**

- **模型层：** CoT + Self-Critique 出题链；自检难度与相关性并自动改写。  
- **逻辑层：** 有限状态机 + 三轴评分决策（追问 / 换题 / 提前结束）+ 摘要记忆。  
- **工程层：** FastAPI 服务化、Redis 会话、异步出题、Docker 与 JSON 可观测性。

**成果（按实测填写）：** 多轮模拟面试 API、结构化回合报告，可作为微服务接入招聘或教学平台。

---

## 可选加分项（Roadmap）

- **提示 Agent：** 候选人卡住时的适度提示  
- **评估校准：** 人工标注数据优化评分 Prompt  
- **成本控制：** 简单轮次小模型、复杂轮次大模型  
- **多租户配额、WebSocket、评估雷达图可视化**

### Celery Worker（可选）

```bash
pip install -e ".[worker]"
# .env 中设置 CELERY_BROKER_URL=redis://localhost:6379/1
celery -A interview_simulator.engineering.celery_app:get_celery_app worker -l info
```

面试结束后若配置 Broker，会异步执行 `interview_simulator.generate_llm_report`；否则由 `BackgroundTasks` / `GET /report` 同步生成。

---

## 许可证

[MIT License](LICENSE)

---

## 说明

本项目强调 **「多 Agent + LangChain + FastAPI + 状态机 + Redis/Docker」** 的完整业务编排；测试默认使用 `tests/test_fakes.py` 中的 Fake Agent，无需真实 API Key。
