"""
MPCI Q&A - FastAPI Web Application
Provides REST API and serves Web UI for the MPCI intelligent Q&A system.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mpci_qa.rag_engine import RAGEngine

# ---------- Logging ----------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mpci-qa")


def load_env_file():
    """Load simple KEY=VALUE settings from project .env for local runs."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


load_env_file()

# ---------- FastAPI App ----------

app = FastAPI(
    title="MPCI 智能问答系统",
    description="UAE MPCI (Maritime Pre-Load Cargo Information) 企业级智能问答客服系统",
    version="1.0.0"
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- RAG Engine ----------

rag_engine = None

def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        # Check environment for LLM type
        llm_type = os.environ.get("MPCI_LLM_TYPE", "auto")
        logger.info(f"Initializing RAG engine (LLM type: {llm_type})...")
        rag_engine = RAGEngine(llm_type=llm_type)
        logger.info("RAG engine ready.")
    return rag_engine


# ---------- API Models ----------

class ChatRequest(BaseModel):
    question: str
    history: Optional[List[Dict]] = None
    top_k: Optional[int] = 5

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict]
    confidence: float


# ---------- API Routes ----------

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "mpci-qa"}


@app.get("/api/info")
async def api_info():
    """Get API information."""
    return {
        "name": "MPCI 智能问答系统",
        "version": "1.0.0",
        "description": "UAE MPCI (Maritime Pre-Load Cargo Information) 企业级智能问答客服系统",
        "knowledge_base": "UAE MPCI Business Specification Document V1.0",
        "llm_type": os.environ.get("MPCI_LLM_TYPE", "auto"),
        "topics": [
            "申报时限 (Filing Timing)",
            "申报角色 (Filer Roles)",
            "业务流程 (Business Processes)",
            "数据要素 (Data Elements)",
            "委托代理 (Delegation)",
            "合并装载 (Consolidation & Co-loading)",
            "提单更新 (Bill of Lading Updates)",
            "货物描述规范 (Goods Description Guidelines)",
            "HS Code 申报",
            "Party ID 使用"
        ]
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Answer a question using RAG."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    engine = get_rag_engine()

    try:
        result = engine.query(
            question=request.question.strip(),
            history=request.history,
            top_k=request.top_k
        )
        return result
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        return ChatResponse(
            answer=f"抱歉，系统处理您的问题时出现错误：{str(e)}",
            sources=[],
            confidence=0.0
        )


@app.get("/api/suggestions")
async def get_suggestions():
    """Get example questions."""
    return {
        "suggestions": [
            "多个 HS Code 怎么申报？",
            "申报截止时间是多久？",
            "收货人应该填什么？",
            "什么是 Consolidation？怎么申报？",
            "收到 Do Not Load 怎么办？",
            "MPCI Party ID 是什么？怎么获取？",
            "我可以委托同行帮我申报吗？",
            "提单更新有什么规则？"
        ]
    }


# ---------- Web UI ----------

WEB_UI = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MPCI 智能问答系统</title>
    <style>
        :root {
            --primary: #1a73e8;
            --primary-dark: #1557b0;
            --bg: #f0f4f9;
            --card-bg: #ffffff;
            --text: #1f1f1f;
            --text-secondary: #5f6368;
            --border: #e0e0e0;
            --user-msg: #e8f0fe;
            --bot-msg: #f8f9fa;
            --success: #34a853;
            --warning: #fbbc04;
            --danger: #ea4335;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            overflow: hidden;
        }

        .app-container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 16px;
        }

        /* Header */
        .header {
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-shrink: 0;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo {
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
        }

        .header h1 {
            font-size: 20px;
            font-weight: 600;
        }

        .header .subtitle {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .llm-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            background: #e8f0fe;
            color: var(--primary);
        }

        /* Status bar */
        .status-bar {
            padding: 8px 0;
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 8px;
            flex-shrink: 0;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            display: inline-block;
        }
        .status-dot.building {
            background: var(--warning);
            animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        /* Chat area */
        .chat-area {
            flex: 1;
            overflow-y: auto;
            padding: 16px 0;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .chat-area::-webkit-scrollbar {
            width: 6px;
        }
        .chat-area::-webkit-scrollbar-thumb {
            background: #ccc;
            border-radius: 3px;
        }

        /* Messages */
        .message {
            max-width: 85%;
            padding: 14px 18px;
            border-radius: 18px;
            line-height: 1.6;
            font-size: 14px;
            animation: fadeIn 0.3s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            background: var(--user-msg);
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }

        .message.bot {
            background: var(--bot-msg);
            align-self: flex-start;
            border-bottom-left-radius: 4px;
            border: 1px solid var(--border);
        }

        .message.bot table {
            width: 100%;
            border-collapse: collapse;
            margin: 8px 0;
            font-size: 13px;
        }

        .message.bot th, .message.bot td {
            border: 1px solid var(--border);
            padding: 6px 10px;
            text-align: left;
        }

        .message.bot th {
            background: #f0f4f9;
            font-weight: 600;
        }

        .message.bot code {
            background: #e8e8e8;
            padding: 1px 5px;
            border-radius: 4px;
            font-size: 13px;
        }

        .message.bot strong {
            font-weight: 600;
        }

        .message.bot ul, .message.bot ol {
            padding-left: 20px;
            margin: 6px 0;
        }

        .message .timestamp {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 8px;
        }

        /* Sources */
        .sources {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px dashed var(--border);
            font-size: 12px;
        }

        .sources-title {
            color: var(--text-secondary);
            margin-bottom: 4px;
            font-weight: 500;
        }

        .source-tag {
            display: inline-block;
            padding: 2px 8px;
            margin: 2px 4px 2px 0;
            background: #e8f0fe;
            border-radius: 10px;
            font-size: 11px;
            color: var(--primary);
        }

        /* Welcome message */
        .welcome {
            text-align: center;
            padding: 40px 20px;
            color: var(--text-secondary);
        }

        .welcome h2 {
            font-size: 22px;
            color: var(--text);
            margin-bottom: 8px;
        }

        .welcome p {
            margin-bottom: 20px;
        }

        .suggestion-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
        }

        .suggestion-chip {
            padding: 8px 16px;
            border: 1px solid var(--border);
            border-radius: 20px;
            background: white;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
            color: var(--text);
        }

        .suggestion-chip:hover {
            border-color: var(--primary);
            color: var(--primary);
            background: #e8f0fe;
        }

        /* Input area */
        .input-area {
            padding: 12px 0 20px;
            border-top: 1px solid var(--border);
            flex-shrink: 0;
        }

        .input-wrapper {
            display: flex;
            gap: 8px;
            background: white;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 4px;
            transition: border-color 0.2s;
        }

        .input-wrapper:focus-within {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.15);
        }

        .input-wrapper input {
            flex: 1;
            border: none;
            outline: none;
            padding: 10px 14px;
            font-size: 15px;
            background: transparent;
            color: var(--text);
        }

        .input-wrapper button {
            padding: 10px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s;
            white-space: nowrap;
        }

        .input-wrapper button:hover {
            background: var(--primary-dark);
        }

        .input-wrapper button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        /* Loading indicator */
        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 8px 0;
        }

        .typing-indicator span {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ccc;
            animation: bounce 1.4s ease-in-out infinite;
        }

        .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
        .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-6px); }
        }

        /* Responsive */
        @media (max-width: 640px) {
            .app-container { padding: 0 8px; }
            .message { max-width: 95%; font-size: 13px; }
            .header h1 { font-size: 16px; }
            .input-wrapper button { padding: 10px 16px; }
        }

        .kb-status { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

        /* Error animation */
        .message.error {
            background: #fce8e6;
            border-color: var(--danger);
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Header -->
        <header class="header">
            <div class="header-left">
                <div class="logo">M</div>
                <div>
                    <h1>MPCI 智能问答系统</h1>
                    <div class="subtitle">UAE Maritime Pre-Load Cargo Information</div>
                </div>
            </div>
            <div>
                <span class="llm-badge" id="llmBadge">模板模式</span>
            </div>
        </header>

        <!-- Status -->
        <div class="status-bar">
            <span class="status-dot building" id="statusDot"></span>
            <span id="statusText">正在初始化知识库...</span>
            <span class="kb-status" id="kbStatus"></span>
        </div>

        <!-- Chat Area -->
        <div class="chat-area" id="chatArea">
            <div class="welcome" id="welcome">
                <h2>👋 欢迎使用 MPCI 智能问答系统</h2>
                <p>基于 UAE MPCI Business Specification Document V1.0<br>为您解答关于阿联酋海事预装货物信息计划的各种问题</p>
                <div class="suggestion-chips" id="suggestionChips">
                    <div class="suggestion-chip" data-q="多个 HS Code 怎么申报？">📦 多个 HS Code</div>
                    <div class="suggestion-chip" data-q="申报截止时间是多久？">⏰ 申报时限</div>
                    <div class="suggestion-chip" data-q="收货人应该填什么？">👤 收货人填写</div>
                    <div class="suggestion-chip" data-q="什么是 Consolidation？怎么申报？">📊 Consolidation</div>
                    <div class="suggestion-chip" data-q="收到 Do Not Load 怎么办？">🚫 Do Not Load</div>
                    <div class="suggestion-chip" data-q="MPCI Party ID 是什么？">🆔 Party ID</div>
                </div>
            </div>
        </div>

        <!-- Input -->
        <div class="input-area">
            <div class="input-wrapper">
                <input type="text" id="questionInput" placeholder="请输入您的 MPCI 相关问题..." maxlength="500"
                       autocomplete="off">
                <button id="sendBtn" onclick="sendMessage()">提问</button>
            </div>
        </div>
    </div>

    <script>
        // ---------- State ----------
        let conversationHistory = [];
        let isLoading = false;
        let isReady = false;

        // ---------- DOM elements ----------
        const chatArea = document.getElementById('chatArea');
        const welcome = document.getElementById('welcome');
        const input = document.getElementById('questionInput');
        const sendBtn = document.getElementById('sendBtn');
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const kbStatus = document.getElementById('kbStatus');

        // ---------- Suggestion chips ----------
        document.getElementById('suggestionChips').addEventListener('click', (e) => {
            const chip = e.target.closest('.suggestion-chip');
            if (chip && chip.dataset.q) {
                input.value = chip.dataset.q;
                sendMessage();
            }
        });

        // ---------- Enter key ----------
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // ---------- Send message ----------
        async function sendMessage() {
            const question = input.value.trim();
            if (!question || isLoading) return;

            input.value = '';
            isLoading = true;
            sendBtn.disabled = true;

            // Hide welcome
            welcome.style.display = 'none';

            // Add user message
            addMessage('user', question);

            // Add loading indicator
            const loadingId = addLoading();

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: question,
                        history: conversationHistory.slice(-10),  // Last 10 turns
                        top_k: 5
                    })
                });

                const data = await response.json();

                // Remove loading
                removeLoading(loadingId);

                // Add bot response
                addBotMessage(data.answer, data.sources || [], data.confidence);

                // Update history
                conversationHistory.push({ role: 'user', content: question });
                conversationHistory.push({ role: 'assistant', content: data.answer });

            } catch (err) {
                removeLoading(loadingId);
                addMessage('bot error', `抱歉，系统出了点问题：${err.message}。请重试。`);
            } finally {
                isLoading = false;
                sendBtn.disabled = false;
                input.focus();
            }
        }

        // ---------- Add message to chat ----------
        function addMessage(role, content) {
            const div = document.createElement('div');
            div.className = `message ${role}`;

            const now = new Date();
            const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

            if (role === 'user') {
                div.innerHTML = `${escapeHtml(content)}<div class="timestamp">${timeStr}</div>`;
            } else {
                // Bot messages use markdown-like rendering
                div.innerHTML = `${renderContent(content)}<div class="timestamp">${timeStr}</div>`;
            }

            chatArea.appendChild(div);
            scrollToBottom();
            return div;
        }

        function addBotMessage(content, sources, confidence) {
            const div = document.createElement('div');
            div.className = 'message bot';

            const now = new Date();
            const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

            let html = renderContent(content);

            html += `<div class="timestamp">${timeStr}</div>`;
            div.innerHTML = html;
            chatArea.appendChild(div);
            scrollToBottom();
        }

        function addLoading() {
            const id = 'loading-' + Date.now();
            const div = document.createElement('div');
            div.className = 'message bot';
            div.id = id;
            div.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;
            chatArea.appendChild(div);
            scrollToBottom();
            return id;
        }

        function removeLoading(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        }

        function scrollToBottom() {
            setTimeout(() => { chatArea.scrollTop = chatArea.scrollHeight; }, 50);
        }

        // ---------- Content rendering ----------
        function renderContent(text) {
            if (!text) return '';

            let html = text;

            // Bold
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

            // Code
            html = html.replace(/`(.+?)`/g, '<code>$1</code>');

            // Line breaks
            html = html.replace(/\n/g, '<br>');

            // Tables (simple)
            html = html.replace(/\|([^\|]+)\|/g, function(match) {
                // Check if inside a table context
                return match;
            });

            return html;
        }

        // ---------- Escape HTML ----------
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // ---------- Initialize ----------
        async function init() {
            try {
                const res = await fetch('/api/info');
                const info = await res.json();

                statusText.textContent = '知识库已就绪 ✓';
                statusDot.className = 'status-dot';

                // Get LLM mode
                const badge = document.getElementById('llmBadge');
                badge.textContent = `${info.llm_type || 'template'} 模式`;

                kbStatus.textContent = `| ${info.knowledge_base || ''}`;
                isReady = true;
                input.focus();

            } catch (err) {
                statusText.textContent = '正在连接服务...';
                statusDot.className = 'status-dot building';
                setTimeout(init, 2000);
            }
        }

        init();
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Serve the web UI."""
    return WEB_UI


# ---------- Main entry point ----------

def main():
    import uvicorn

    host = os.environ.get("MPCI_HOST", "0.0.0.0")
    port = int(os.environ.get("MPCI_PORT", "8000"))

    logger.info(f"Starting MPCI Q&A Server on {host}:{port}")
    logger.info(f"Open http://localhost:{port} in your browser")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
