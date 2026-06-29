# MPCI申报助手系统

这是一个面向 UAE MPCI（Maritime Pre-Load Cargo Information）的申报助手系统。项目基于 FastAPI 提供 Web 页面和 REST API，通过 ChromaDB 向量库检索《UAE MPCI Business Specification Document V1.0》的知识片段，再交给 LLM 或内置模板生成回答。

## 功能概览

- Web 聊天页面：`http://localhost:8000`
- 健康检查：`GET /health`
- 文档问答：`POST /api/chat`
- 示例问题：`GET /api/suggestions`
- 支持 DeepSeek / OpenAI 兼容接口、Claude 接口，以及无外部模型的 `template` 模式
- 针对中文常见问法做了业务主题路由和检索增强，例如“申报截止时间是多久？”会优先召回 §3.3 `Filing Timing`
- 回答会先判断申报场景、角色、提单层级或操作动作，再给出业务建议
- Web 页面默认不展示参考来源；`sources` 仍会在 API 响应中保留，方便调试和评估
- 内置检索评估集，可验证常见问题是否命中正确手册章节

## 项目结构

```text
MPCI/
├─ mpci_qa/                     # 应用核心代码
│  ├─ app.py                    # FastAPI 应用、API 路由、内置 Web UI
│  ├─ server.py                 # 生产/容器启动入口
│  ├─ rag_engine.py             # RAG 编排与回答生成
│  ├─ vector_store.py           # ChromaDB 向量库构建、加载、检索
│  ├─ knowledge_base.py         # 从 pdf_text.txt 构建知识分块
│  ├─ business_topics.py        # 业务主题识别、查询扩展、必需章节配置
│  ├─ chunks/mpci_chunks.json   # 知识分块索引摘要
│  └─ vector_store/             # 已构建的 ChromaDB 本地向量库
├─ scripts/evaluate_retrieval.py # 检索评估脚本
├─ tests/eval_questions.json    # 标准业务问题评估集
├─ pdf_text.txt                 # 从 MPCI 业务规范 PDF 提取的文本
├─ TEST/                        # 测试样例、测试提单等资料
├─ TEMP/                        # 原始业务资料、规范文档、培训资料等
├─ .env.example                 # 环境变量示例
├─ requirements.txt             # Python 依赖清单
├─ Dockerfile                   # Docker 部署配置
├─ start_mpci.bat               # Windows 快速启动脚本
└─ README.md                    # 项目说明
```

## 环境要求

- Python 3.12+
- Windows / Linux / macOS 均可运行
- 如使用 DeepSeek、OpenAI 或 Claude，需要可用的 API Key

安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

复制配置示例：

```bash
copy .env.example .env
```

按实际情况修改 `.env`：

```env
MPCI_LLM_TYPE=auto
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

MPCI_HOST=0.0.0.0
MPCI_PORT=8000
MPCI_WORKERS=1
```

LLM 类型说明：

- `auto`：自动检测 `.env` 中的 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`，优先使用真实模型
- `openai`：使用 OpenAI SDK，可连接 OpenAI 或 DeepSeek 等 OpenAI-compatible 服务
- `claude`：使用 Claude API，需额外安装 `anthropic`
- `template`：不调用外部模型，只使用内置规则模板，适合离线演示；复杂业务问题不建议长期使用该模式

注意：不要把真实 `.env` 或 API Key 提交到版本库。

## 启动方式

开发启动：

```bash
python -m mpci_qa.app
```

生产/配置化启动：

```bash
python -m mpci_qa.server
```

Windows 快速启动：

```bat
start_mpci.bat
```

启动后访问：

```text
http://localhost:8000
```

检查服务是否正常：

```bash
curl http://localhost:8000/health
```

正常返回：

```json
{"status":"ok","service":"mpci-qa"}
```

## API 示例

请求：

```bash
curl -X POST http://localhost:8000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"申报截止时间是多久？\",\"top_k\":5}"
```

响应字段：

- `answer`：回答内容
- `sources`：召回的内部参考章节，仅用于调试和评估；Web 页面默认不展示
- `confidence`：最高召回分数

## 知识库与检索

知识来源是根目录的 `pdf_text.txt`。`knowledge_base.py` 会根据手册目录页码映射构建章节分块，并尽量按章节标题截取精确内容，避免同一页多个章节互相污染。`vector_store.py` 会将分块写入 `mpci_qa/vector_store/`。

如果需要重建知识库：

```bash
python -m mpci_qa.knowledge_base
python -m mpci_qa.vector_store
```

当前检索层包含业务主题路由，解决默认英文 embedding 对中文业务问题召回不足的问题。比如中文“截止时间 / 时限 / 多久 / 提前”会追加英文业务词 `Filing Timing`、`24 Hours Pre-load`、`6 Hours Pre-load` 做合并检索，并对 §3.3 做轻微加权。

对已知高风险问题，`rag_engine.py` 会检查是否召回了业务主题要求的关键章节。如果没有命中，会按章节号补拉权威上下文，再交给模型生成回答。

## 评估

项目内置了一个轻量检索评估集：

```bash
python scripts/evaluate_retrieval.py
```

评估数据在 `tests/eval_questions.json`，每条问题包含：

- `question`：测试问题
- `expected_sections`：应该命中的手册章节
- `must_contain`：答案或上下文建议包含的关键业务词

当前评估集覆盖：

- 申报时限
- 收货人 / To Order
- HS Code 和货物描述
- 委托申报
- 船代委托
- Consolidation / Co-loading
- DNL / RFI
- MPCI Party ID
- 提单更新 / Split Bill

## Docker 部署

构建镜像：

```bash
docker build -t mpci-qa .
```

运行：

```bash
docker run -d -p 8000:8000 --env-file .env mpci-qa
```

## 常见问题

### 问“申报截止时间”却回答找不到

这是中文问题没有正确召回 §3.3 `Filing Timing` 导致的。当前版本已经在 `vector_store.py` 中增加查询扩展和章节加权。若服务仍返回旧答案，请重启服务。

### 页面显示“模板模式”

页面右上角会显示当前后端 `llm_type`。实际后端模式由 `MPCI_LLM_TYPE` 决定，也可查看启动日志中的 `LLM type`。

### 修改 `.env` 后不生效

环境变量只在服务启动时读取。修改配置后需要重启服务。

## 开发备注

- `app.py` 内置了完整 HTML/CSS/JS 页面，当前没有独立前端构建步骤。
- `rag_engine.py` 同时支持 LLM 生成和模板兜底。
- `business_topics.py` 是当前可靠性改造的核心配置，新增业务问题类型时应优先在这里维护关键词、英文扩展查询和必需章节。
- `vector_store/` 是本地持久化向量库；如果删除，首次查询或重建流程会重新构建。
- 运行日志如 `mpci_server.err.log`、`mpci_server.out.log` 属于本地运行产物，已加入 `.gitignore`。
