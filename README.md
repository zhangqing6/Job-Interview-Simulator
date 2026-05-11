# 智能面试官 Agent —— 基于 LangChain 的多轮情境面试系统

**英文名：** Multi-Agent Job Interview Simulator with Automated Evaluation

模拟真实技术面试流程：Agent 根据**职位描述**与**候选人简历**动态提问、追问、评估回答质量，并输出**结构化反馈**。支持多候选人、多面试维度与流程配置。

---

## 一句话亮点（简历 / 面试口述）

> 不是单次对话循环，而是 **状态机驱动的多轮面试**：动态追问、跑题检测、提前终止、多维度评分，并以 **FastAPI + Redis** 服务化落地，可对接招聘或实训平台。

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 动态出题 | 基于 JD + 简历生成有逻辑、有深度的技术问题 |
| 追问与纠偏 | 回答过浅或跑偏时自然追问；严重跑题时可切换问题 |
| 结构化评估 | 技术正确性、表达清晰度、完整性等多维度打分 |
| 最终报告 | 综合评分 + 可执行的改进建议 |
| 会话与并发 | Redis 会话隔离；异步接口支撑多路面试 |

---

## 架构分层

### 1. 模型能力层（Model Capability）

**核心任务：** 出题 → 判题难度与相关性 → 评估回答 → 生成报告。

**设计原则：** 避免「一轮 Prompt 包打天下」，采用 **Chain-of-Thought（CoT）+ Self-Critique** 等多步编排：

1. 生成面试问题  
2. 自检：难度 / 挑战性是否足够  
3. 不足则自动改写问题  

**Prompt 策略实验（可写进简历）：** Zero-shot / Few-shot / CoT / Self-ask 等对比，提升问题质量与评分一致性。

**模型可选：** GPT-4、Claude 3.5 Sonnet，或本地开源模型（如 Llama 3）。

---

### 2. 业务逻辑层（Business Logic）

**① 面试状态机**

典型状态（可按实现微调命名）：`initial` → `questioning` → `waiting_for_answer` → `evaluating` → `follow_up` → `next_question` → `finalize`。

每个状态绑定不同的 Prompt、工具策略与分支逻辑。

**② 评分与决策模块（非简单加权）**

对每轮回答做结构化评分，例如：

- 技术深度：1–5  
- 表达清晰度：1–5  
- 与问题相关性：1–5  

**动态决策示例：**

- 分数偏低 → 是否追问  
- 严重跑题 → 是否换题  
- 连续多轮低分 → 是否提前结束面试  

**③ 多轮记忆管理**

不单靠堆满 `history`：采用 **摘要记忆 + 关键事实抽取**，控制 token、降低噪声。

**④ 多 Agent（可选进阶）**

- 主面试官 Agent：提问与节奏  
- 评分 Agent：独立评估，减少「既当裁判又当选手」  
- 提示 Agent：候选人卡住时适度提示，贴近真实面试  

---

### 3. 落地工程层（Engineering）

| 组件 | 用途 |
|------|------|
| **Python** | 主语言 |
| **LangChain** | LCEL 编排、Memory、Chains、Runnables |
| **FastAPI** | HTTP 服务与文档 |
| **Pydantic** | 会话状态、得分、报告等强类型校验 |
| **Redis** | 会话与缓存，支撑多轮、多候选人 |
| **Docker** | 一键构建与部署 |

**工程要点：**

- **自定义 Interview Agent**：`question_chain`、`evaluation_chain`、`follow_up_chain` 等与状态机协同  
- **异步**：模型调用耗时可用 `asyncio` + `BackgroundTasks`；规模更大时可引入 Celery  
- **可观测性**：记录每次调用的 prompt / response / token；结构化日志（如 JSON Lines）便于分析与调参  
- **测试**：状态机与评分规则单元测试；端到端集成测试；固定 seed + 温度 0 做输出稳定性回归  

---

## API 设计（示例）

与服务实现保持一致即可，以下为常见划分：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/interview/start` | 创建会话（JD、简历、维度配置等） |
| `POST` | `/interview/ask` | 提交候选人回答，返回下一问 / 追问 / 阶段性反馈 |
| `GET` | `/interview/status/{id}` | 当前阶段与状态机快照 |
| `GET` | `/interview/report/{id}` | 最终评分与结构化报告 |

---

## 快速开始（规划）

### 环境变量（示例）

```bash
OPENAI_API_KEY=your_key
REDIS_URL=redis://localhost:6379/0
```

### Docker（规划）

```bash
docker compose up --build
```

具体 `Dockerfile` / `docker-compose.yml` 以实现为准。

---

## 简历表述参考（可直接微调数字与成果）

**项目名称：** 智能面试 Agent —— 基于 LangChain 的多轮情境面试系统  

**技术栈：** Python, LangChain, FastAPI, Redis, Docker, OpenAI GPT-4（或实际所用模型）

**核心贡献：**

- **模型层：** 设计 Chain-of-Thought + Self-Critique 提示策略，对比多种 Prompt 方案，提升问题难度与评分一致性（可量化自测指标）。  
- **逻辑层：** 基于有限状态机控制面试流程，支持动态追问、提前终止、多维度结构化评分，非简单对话循环。  
- **工程层：** FastAPI 服务化，LangChain LCEL 编排，Redis 管理会话，异步并发与 Docker 部署。  

**成果（按实测填写）：** 完成多轮模拟面试与结构化报告输出，可作为独立微服务接入招聘或教学平台。

---

## 可选加分项（Roadmap）

- **流式输出：** SSE 或 WebSocket，模拟面试官逐字输出  
- **多候选人并行：** 会话隔离 + 资源与配额控制  
- **评估校准：** 少量人工标注数据优化评分 Prompt  
- **成本控制：** 简单轮次用小模型，复杂推理用大模型  

---

## 许可证

以仓库内 `LICENSE` 为准（若尚未添加，请按需补充）。

---

## 说明

本项目强调 **「LangChain + FastAPI + 状态机 + 服务化」** 的组合：体现真实业务编排与工程落地能力，而非仅调用大模型 API。
