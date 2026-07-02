"""
MPCI RAG Engine
Retrieves relevant context from vector store and generates answers.
Currently uses a template-based approach for PoC; designed for easy LLM integration.
"""

import os
import re
from typing import List, Dict, Optional
from . import vector_store
from .business_topics import detect_topics, required_sections


# ---------- Prompt Templates ----------

SYSTEM_PROMPT = """你是一个专业的阿联酋 MPCI（海事预装货物信息计划）申报顾问。
你的目标不是复述资料，而是帮助用户判断当前属于哪类申报场景，并给出可执行的处理建议。

回答准则：
1. 先判断用户问题可能对应的申报场景、角色、提单层级或操作动作，再组织答案
2. 严格基于提供的内部规则内容回答，不要编造信息
3. 不要在用户答案中说“根据文档/手册/参考资料/章节/来源”
4. 不要把引用来源、章节号、页码暴露给用户，除非用户明确要求
5. 若问题信息不足，先说明你当前按什么场景假设，并列出需要确认的信息
6. 必须使用用户提问的语言回答：英文问题用英文，中文问题用中文，不要混用
7. 只说明内部规则支持的风险或后果；没有依据时不要主动提罚款、处罚或法律后果
8. 给出可操作的指导，不要只说空话
"""


def infer_scenario(query: str) -> str:
    """Infer a practical declaration scenario from the user question."""
    topics = detect_topics(query)
    scenarios = {
        "filing_timing": "用户在确认某类提单的提交截止时间。需要区分船公司、货代/Sub Co-loader、Master Co-loader，以及 Master B/L、Direct B/L、House B/L。",
        "consignee": "用户在确认收货人字段填写。需要判断提单是否可转让、是否 To Order、是否涉及银行或 consolidation。",
        "hs_code": "用户在确认货物明细申报。需要按 goods item 拆分 HS Code、货描、重量、包装和集装箱装载关系。",
        "delegation": "用户在确认是否可以委托他方申报。需要区分货代之间委托、船公司委托船代、责任委托和申报委托。",
        "consolidation": "用户在处理 consolidation/co-loading。需要判断 Master B/L、House B/L、Master Co-loader、Sub Co-loader 的层级关系和 Party ID 传递。",
        "assessment": "用户在处理 NAIC 响应状态。需要区分 DNL、RFI、PSF、ACT/ACW，以及响应位于 Master 层还是 House 层。",
        "party_id": "用户在确认 MPCI Party ID 的获取、共享或使用场景。需要区分申报方自己的 ID、委托方 ID、链路中相关方 ID。",
        "update": "用户在处理提单更新、变更、Switch Bill 或 Split Bill。需要判断是更正、航次变更、拆分、合并还是响应 RFI。",
    }
    matched = [scenarios[t] for t in topics if t in scenarios]
    if matched:
        return "\n".join(f"- {item}" for item in matched)
    return "- 用户问题暂未命中明确业务主题。先从申报角色、提单类型、货物流向、操作动作四个维度判断场景；如信息不足，应说明需要补充什么。"


def build_prompt(query: str, context_chunks: List[Dict], conversation_history: List[Dict] = None) -> str:
    """Build a RAG prompt with context."""
    # Format context
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        source = f"[{chunk['title']}]"
        if chunk.get("section_num"):
            source += f" (章节 {chunk['section_num']})"
        context_parts.append(f"--- 参考资料 {i+1}: {source} ---\n{chunk['content']}\n")

    context_text = "\n\n".join(context_parts)

    # Format conversation history
    history_text = ""
    if conversation_history:
        history_parts = []
        for msg in conversation_history[-5:]:  # Last 5 turns
            role = "用户" if msg["role"] == "user" else "助手"
            history_parts.append(f"{role}: {msg['content']}")
        history_text = "\n".join(history_parts)

    prompt = f"""{SYSTEM_PROMPT}

{ f"### 对话历史\n{history_text}\n\n" if history_text else "" }### 参考资料
以下是系统内部检索到的规则内容，只用于你判断和回答，不要向用户暴露“参考资料/章节/文档来源”等措辞：

{context_text}

### 场景判断提示
{infer_scenario(query)}

### 用户问题
{query}

### 回答要求
- 内部先判断申报场景，但不要向用户输出“我会按什么场景判断”
- 直接给出业务结论；如果信息不足，只说明需要补充哪些信息
- 必须用和用户问题相同的语言回答
- 分点说明（如有需要）
- 给出具体的操作建议
- 不要主动提罚款、处罚、法律后果，除非内部规则内容明确支持
- 不要输出“根据文档/根据手册/参考章节/参考来源”等话术

### Output language
{_output_language_instruction(query)}
"""

    return prompt


def _output_language_instruction(query: str) -> str:
    ascii_letters = sum(1 for char in query if char.isascii() and char.isalpha())
    cjk_chars = sum(1 for char in query if "\u4e00" <= char <= "\u9fff")
    if ascii_letters > cjk_chars * 2:
        return "Answer in English only. Do not answer in Chinese."
    return "请只使用中文回答。"


# ---------- LLM Integration ----------

class LLMBackend:
    """LLM backend abstraction. Currently uses rule-based fallback."""

    def __init__(self, model_type: str = "auto"):
        self.model_type = model_type
        self.answer_mode = "template"
        self._init_llm()

    def _init_llm(self):
        """Initialize the actual LLM if configured."""
        if self.model_type == "auto":
            if os.environ.get("OPENAI_API_KEY"):
                self.model_type = "openai"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                self.model_type = "claude"
            else:
                self.model_type = "template"

        if self.model_type == "openai":
            self._init_openai()
        elif self.model_type == "claude":
            self._init_claude()
        else:
            print("Using template-based response generation (no external LLM API)")

    def _init_openai(self):
        """Initialize OpenAI client."""
        if not os.environ.get("OPENAI_API_KEY"):
            print("WARNING: OPENAI_API_KEY is not set. Falling back to template mode.")
            self.model_type = "template"
            return

        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            )
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            self.answer_mode = "llm"
            print(f"OpenAI client initialized with model: {self.model}")
        except ImportError:
            print("WARNING: openai package not installed. Install with: pip install openai")
            self.model_type = "template"

    def _init_claude(self):
        """Initialize Claude API client."""
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("WARNING: ANTHROPIC_API_KEY is not set. Falling back to template mode.")
            self.model_type = "template"
            return

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            self.answer_mode = "llm"
            print(f"Claude client initialized with model: {self.model}")
        except ImportError:
            print("WARNING: anthropic package not installed. Install with: pip install anthropic")
            self.model_type = "template"

    def generate(self, prompt: str) -> str:
        """Generate a response."""
        if self.model_type == "template":
            return self._template_response(prompt)
        elif self.model_type == "openai":
            return self._openai_response(prompt)
        elif self.model_type == "claude":
            return self._claude_response(prompt)
        else:
            return self._template_response(prompt)

    def _openai_response(self, prompt: str) -> str:
        """Call OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            return self._polish_answer(response.choices[0].message.content, prompt)
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return self._template_response(prompt)

    def _claude_response(self, prompt: str) -> str:
        """Call Claude API."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            return self._polish_answer(response.content[0].text, prompt)
        except Exception as e:
            print(f"Claude API Error: {e}")
            return self._template_response(prompt)

    def _template_response(self, prompt: str) -> str:
        """
        Template-based response generator for PoC.
        Extracts relevant context and presents it in a readable format.
        """
        # Extract the query
        query_match = re.search(r'### 用户问题\n(.+?)(?:\n|$)', prompt)
        query = query_match.group(1).strip() if query_match else ""

        # Extract context chunks
        context_sections = re.findall(r'参考资料 \d+: (.+?) \((章节.+?)\)', prompt)
        context_refs = "\n".join([f"  - {s}" for s in context_sections])

        # Extract the actual context content for key information
        context_text = ""
        context_match = re.search(r'参考资料\n(.+?)(?=\n### 用户问题)', prompt, re.DOTALL)
        if context_match:
            context_text = context_match.group(1)[:2000]

        # Build a simple response based on patterns
        answer = self._pattern_match(query, context_text)

        return self._polish_answer(answer, prompt)

    def _polish_answer(self, answer: str, prompt: str) -> str:
        """Make generated answers read like business advice, not document citations."""
        query_match = re.search(r'### 用户问题\n(.+?)(?:\n|$)', prompt)
        query = query_match.group(1).strip() if query_match else ""
        answer = re.sub(r'根据\s*MPCI\s*业务规范(?:文档)?第[^：:\n]+[：:]\s*', '', answer)
        answer = re.sub(r'根据\s*MPCI\s*业务规范(?:文档)?[^。；;\n]*[。；;]?\s*', '', answer)
        answer = re.sub(r'>\s*参考章节[^\n]*', '', answer)
        answer = re.sub(r'参考章节[：:][^\n]*', '', answer)
        cleaned_lines = []
        for line in answer.splitlines():
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append(line)
                continue
            if stripped.startswith("根据 MPCI") or stripped.startswith("根据MPCI"):
                continue
            if stripped.startswith("根据规则") or stripped.startswith("根据相关规则"):
                line = stripped.replace("根据相关规则，", "").replace("根据规则，", "")
                stripped = line.strip()
            if any(term in stripped for term in ["文档中", "手册中", "从文档", "从手册", "资料中"]):
                continue
            if stripped.startswith("> 您的问题涉及"):
                continue
            if stripped.startswith("> 参考") or stripped.startswith("参考章节"):
                continue
            if "参考章节" in stripped or "参考来源" in stripped:
                continue
            if "请参考" in stripped or "如需更精确的信息" in stripped:
                continue
            if "MIG" in stripped or "Message Implementation Guide" in stripped:
                continue
            if "本文档" in stripped or "业务规范文档" in stripped:
                continue
            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines).strip()
        cleaned = re.sub(r'^根据\s*MPCI\s*业务规范(?:文档)?第[^：:]+[：:]\s*', '', cleaned)
        cleaned = re.sub(r'^根据\s*MPCI\s*业务规范(?:文档)?中的相关内容[：:]\s*', '', cleaned)
        cleaned = re.sub(r'^根据[^。\n]*(?:文档|手册|参考资料|业务规范)[^。\n]*[：:]\s*', '', cleaned)

        return cleaned

    def _pattern_match(self, query: str, context: str) -> str:
        """Simple pattern matching to extract relevant answers."""
        q = query.lower()
        is_english = self._is_english_query(query)

        # Determine question category
        if self._is_hbl_requirement_question(q):
            return self._answer_hbl_requirements(query, context)
        elif any(k in q for k in ["hs code", "hs编码", "海关编码", "商品编码"]):
            return self._answer_hs_code_en(context) if is_english else self._answer_hs_code(context)
        elif any(k in q for k in ["收货人", "consignee", "to order"]):
            return self._answer_consignee_en(context) if is_english else self._answer_consignee(context)
        elif any(k in q for k in ["时限", "cut-off", "截止", "几小时", "多久", "提前", "最晚"]) or ("direct" in q and "b/l" in q and any(k in q for k in ["when", "time", "deadline", "最晚", "申报"])):
            return self._answer_timing_en(context) if is_english else self._answer_timing(context)
        elif any(k in q for k in ["party id", "mpci party id"]):
            return self._answer_party_id_en(context) if is_english else self._answer_party_id(context)
        elif any(k in q for k in ["委托", "delegation", "代理", "代申报"]):
            return self._answer_delegation_en(context) if is_english else self._answer_delegation(context)
        elif any(k in q for k in ["psf", "pending sub filing"]):
            return self._answer_psf_en(context) if is_english else self._answer_psf(context)
        elif self._is_forwarder_child_cargo_question(q):
            return self._answer_forwarder_child_cargo(context)
        elif any(k in q for k in ["consolidation", "合并", "co-load", "拼柜"]):
            return self._answer_consolidation_en(context) if is_english else self._answer_consolidation(context)
        elif any(k in q for k in ["dnl", "do not load", "不装", "拒绝"]):
            return self._answer_dnl_en(context) if is_english else self._answer_dnl(context)
        elif any(k in q for k in ["rfi", "request for information", "补料"]):
            return self._answer_rfi_en(context) if is_english else self._answer_rfi(context)
        elif any(k in q for k in ["更新", "update", "修改", "amend", "变更"]):
            return self._answer_update_en(context) if is_english else self._answer_update(context)
        elif any(k in q for k in ["split", "分单", "分批"]):
            return self._answer_split_en(context) if is_english else self._answer_split(context)
        elif any(k in q for k in ["重量", "weight", "体积", "package", "包装"]):
            return self._answer_goods_en(context) if is_english else self._answer_goods(context)
        elif any(k in q for k in ["general cargo", "commodity", "goods description"]):
            return self._answer_goods_en(context) if is_english else self._answer_goods(context)
        elif any(k in q for k in ["谁", "角色", "申报", "filer", "责任"]):
            return self._answer_roles_en(context) if is_english else self._answer_roles(context)
        else:
            return self._answer_general(query, context)

    def _is_forwarder_child_cargo_question(self, q: str) -> bool:
        has_forwarder = any(k in q for k in ["货代", "freight forwarder", "nvocc"])
        has_child_party = any(k in q for k in ["下层", "下家", "同行", "sub co-loader", "sub-co-loader", "给我货", "给我货物"])
        has_bl_issue = any(k in q for k in [
            "提单号", "提单", "bill number", "bl number", "b/l number",
            "不需要我生成", "不生成", "不需要我签发", "不签发", "签发",
            "自己的提单", "出单", "开单"
        ])
        asks_filing = any(k in q for k in ["申报", "filing", "怎么做", "怎么处理"])
        return has_forwarder and has_child_party and (has_bl_issue or asks_filing)

    def _is_hbl_requirement_question(self, q: str) -> bool:
        has_hbl = any(k in q for k in ["hbl", "house bill", "house b/l", "house bl", "house bill of lading"])
        asks_required = any(k in q for k in [
            "mandatory", "required", "special document", "document mandatory",
            "需要什么资料", "强制", "必填", "最低资料", "需要什么文件"
        ])
        mentions_general_info = any(k in q for k in [
            "general information", "minimum hs code", "commodity details",
            "cnee detail", "shipper detail", "资料不全", "基础信息", "笼统"
        ])
        return has_hbl and (asks_required or mentions_general_info)

    def _extract_from_context(self, context: str, keyword: str, max_chars: int = 500) -> str:
        """Extract relevant sentences around a keyword from context."""
        idx = context.lower().find(keyword.lower())
        if idx == -1:
            return ""

        # Get surrounding text
        start = max(0, idx - 100)
        end = min(len(context), idx + 400)
        return context[start:end]

    def _answer_hs_code(self, context: str) -> str:
        return """根据 MPCI 业务规范文档第 5.1 节（Business Data Elements）和附录 D（Goods Description Guidelines）：

## 多个 HS Code 的处理方式

**需要按货物项目拆分申报，不能只发一个 HS Code。**

### 具体要求

| 字段 | 处理方式 |
|------|---------|
| **HS Code** | 每个不同的商品类别分别申报对应的 HS Code |
| **Goods Description** | 每个 HS Code 对应详细的货物描述（参见附录 D 规范） |
| **Goods Weight** | 每个货物项目的重量分别申报 |
| **Package Type/Quantity** | 每个货物项目的包装类型和数量分别申报 |
| **Container Goods Placement** | 指定每个集装箱内装有哪些货物项目 |

> 📌 **注意**：这些是业务规范要求，具体报文层面的实现细节（CUSCAR 消息中如何使用循环段）请参考 **MPCI – Message Implementation Guide (MIG)** 文档。
"""

    def _answer_hs_code_en(self, context: str) -> str:
        return """If one shipment contains multiple HS Codes, file the cargo by goods item. Do not collapse everything into one generic HS Code.

You should provide, for each goods item:

| Field | What to provide |
|---|---|
| HS Code | The HS Code for that specific commodity |
| Goods description | A clear and specific English description |
| Weight | Weight for that goods item |
| Package type / quantity | Package details for that goods item |
| Container placement | Which container contains which goods item |

Avoid vague descriptions such as "general cargo", "FAK", or "STC". If the shipper cannot provide exact commodity details, ask them to provide the specific commodity name, HS Code, package quantity/type, and gross weight before filing."""

    def _answer_hbl_requirements(self, query: str, context: str) -> str:
        if self._is_english_query(query):
            return """For HBL filing, there is normally no separate “special document” that must be uploaded just because it is an HBL. The key point is that the HBL filing must contain enough complete and specific data for MPCI assessment.

If the shipper only provides very general information, that is usually not enough.

## What you should collect before filing

At minimum, make sure you have:

| Area | What to confirm |
|---|---|
| HBL details | HBL number, negotiable / non-negotiable flag, cargo movement type |
| Parties | Shipper name/address, consignee name/address, and any relevant party ID / liable party information |
| Cargo details | Specific goods description, HS Code, package type, package quantity, gross weight |
| Container details | Container number, container type/size, seal number, and which goods are placed in which container |
| Linkage | Parent B/L or upper-layer B/L information if this HBL is under a consolidation/co-loading structure |

## Practical guidance

- Do not file with only vague commodity information such as “general cargo” or a broad description.
- Ask the shipper to provide a specific goods description, HS Code, package quantity/type, gross weight, and full shipper/consignee details.
- If this is a consolidation or co-loading case, confirm the parent B/L and the MPCI Party ID of the relevant parties before filing.
- If the information is incomplete, the filing may trigger validation issues, RFI, pending linkage, or late/incomplete filing risk.

So the answer is: no extra HBL-only special document is normally required, but general information alone is not sufficient. You should collect complete HBL data elements before submission."""

        return """HBL 申报通常不需要额外上传某个“特殊文件”。重点不是文件名称，而是 HBL filing 里必须有足够完整、具体的申报数据。

如果 shipper 只给很笼统的基础信息，通常是不够的。

## 提交前至少要确认这些资料

| 类别 | 需要确认 |
|---|---|
| HBL 信息 | HBL number、是否可转让、货物流向类型 |
| 当事方 | Shipper 名称/地址、Consignee 名称/地址、相关 Party ID / 责任方信息 |
| 货物信息 | 具体货描、HS Code、包装类型、包装数量、毛重 |
| 箱信息 | Container number、箱型尺寸、seal number、货物装在哪个箱 |
| 链路关系 | 如果是 consolidation/co-loading，需要 parent B/L 或上层 B/L 信息 |

## 操作建议

- 不建议用 “general cargo” 或过于笼统的 commodity description 去申报。
- 先向 shipper 补齐具体货描、HS Code、包装、重量、收发货人等信息。
- 如果是拼箱或多层提单，还要确认 parent B/L 和相关方 MPCI Party ID。
- 信息不足可能导致校验错误、RFI、关联 pending，或迟报/资料不完整风险。

所以结论是：HBL 没有额外的特殊文件要求，但 general information alone 不足以安全申报；你需要补齐完整 HBL 数据后再提交。"""

    def _is_english_query(self, query: str) -> bool:
        ascii_letters = sum(1 for char in query if char.isascii() and char.isalpha())
        cjk_chars = sum(1 for char in query if "\u4e00" <= char <= "\u9fff")
        return ascii_letters > max(10, cjk_chars * 2)

    def _looks_chinese(self, text: str) -> bool:
        sample = text[:300]
        cjk_chars = sum(1 for char in sample if "\u4e00" <= char <= "\u9fff")
        return cjk_chars >= 12

    def _answer_consignee(self, context: str) -> str:
        return """根据 MPCI 业务规范第 5.2 节（Handling Consignee Data Element Scenarios）和附录 C（Party Information Guidelines）：

## 收货人（Consignee）填写规则

### 不可转让提单（Non-Negotiable B/L）
| 要求 | 说明 |
|------|------|
| ✅ 收货人必须填写 | 必须提供最终收货人的名称和地址 |
| ❌ 禁止填货代/同行 | 附录C明确禁止填写船公司、货运代理和consolidator信息 |
| ✅ 必须是最终收货人 | 即实际收到货物的一方 |

### 可转让提单（Negotiable B/L）

| 场景 | 收货人字段处理 |
|------|:-------------:|
| **空白背书（To Order）** | **留空**，不要填"To Order" |
| **To Order of a Bank** | **留空**，银行名称填入"Payer on behalf of importer"字段 |
| **To Order of Shipper/第三方** | 填写 Shipper 或该第三方的名称 |

### 关于 Consolidation 场景

如果您是 NVOCC/Master Co-loader（开柜给同行），您申报的提单应标记为 **可转让提单 + 空白背书**，收货人 **留空**。最终收货人信息由您的同行在他们那一层的 House B/L 中提供。

> 参考章节：§5.2, §Appendix C
"""

    def _answer_consignee_en(self, context: str) -> str:
        return """For a To Order B/L, do not enter "To Order" as the consignee name.

Use this rule of thumb:

| B/L scenario | Consignee handling |
|---|---|
| Non-negotiable B/L | Provide the final consignee name and address |
| Blank-endorsed To Order B/L | Leave the consignee field blank |
| To Order of a Bank | Leave consignee blank; put the bank in the payer-on-behalf-of-importer field if required |
| To Order of shipper or another named party | Use that named party as applicable |

If this is a consolidation case, the upper-layer consolidated bill may leave consignee blank, while the lower House B/L should provide the final consignee details."""

    def _answer_timing(self, context: str) -> str:
        return """根据 MPCI 业务规范第 3.3 节（Filing Timing）：

## 申报时限要求

| 角色 | 单证类型 | 截止时间 |
|:----|:---------|:--------:|
| **船公司 (Shipping Line)** | Master B/L（主单） | **装船前 6 小时** |
| | Direct B/L（直单） | **装船前 24 小时** |
| **货代/Sub Co-loader** | 最底层 House B/L | **装船前 24 小时** |
| **Master Co-loader** | Master Co-loader B/L | **装船前 6 小时** |

### 注意事项
- **Late Filing（迟报）** 是数据质量五大支柱之一，会影响风险评评估
- 要求在装船前的最后一个国外离港港**之前**完成申报
- 建议尽早申报，不要踩截止时间

> 参考章节：§3.3, §7
"""

    def _answer_timing_en(self, context: str) -> str:
        return """The filing deadline depends on the role and B/L type:

| Filer / B/L type | Filing deadline |
|---|---|
| Shipping line - Master B/L | 6 hours before loading |
| Shipping line - Direct B/L | 24 hours before loading |
| Freight forwarder / Sub Co-loader - lowest House B/L | 24 hours before loading |
| Master Co-loader B/L | 6 hours before loading |

Use the earlier deadline when you are unsure which level applies. For a Direct B/L, treat the deadline as 24 hours before loading."""

    def _answer_delegation(self, context: str) -> str:
        return """根据 MPCI 业务规范第 4.6 节（Delegation Process）：

## 委托代理机制

### 货代委托 (4.6.1)
货代有几种委托选项：
- **本地货代 → 海外货代**：委托海外货代代为申报
- **Master Co-loader → Sub Co-loader**：上层委托下层
- **Sub Co-loader → Master Co-loader**：下层委托上层

委托方式：在 NAIC 门户注册时选择：
1. 默认允许任何货代代为申报
2. 指定特定货代
3. 完全禁止委托

**关键**：委托方必须手动将 MPCI Party ID 分享给被委托方。

### 船公司委托给船代 (4.6.2)
- **责任委托**：每个酋长国最多 1 个代理
- **申报委托**：可委托 1 个或多个代理
- **两者同时委托**：无本地代表 + 无直接对接

### NAIC 响应
- 主要响应发给 **实际申报方**
- 委托方可通过 NAIC 门户查看所有申报状态

> 参考章节：§4.6
"""

    def _answer_delegation_en(self, context: str) -> str:
        return """Delegation is allowed, but the filing role and responsibility must remain clear.

For freight forwarders, delegation can happen between local and overseas forwarders, or between Master Co-loader and Sub Co-loader. The delegating party must share its MPCI Party ID with the party that will file on its behalf.

Practical steps:

1. Confirm who is the actual B/L issuer.
2. Confirm who will submit the MPCI filing.
3. Share the required MPCI Party ID with the delegated filer.
4. Make sure the filing reflects the correct issuer and parent/child B/L relationship.

Delegation does not mean inventing a new B/L number or changing the actual issuer of the bill."""

    def _answer_consolidation(self, context: str) -> str:
        return """根据 MPCI 业务规范第 6.1 节（Consolidation and Co-loading）：

## 合并装载申报要求

### 核心原则
NAIC 要求提交**所有层级**的提单，实现全程可追溯。

### 示例：三层结构
```
船公司 ── 签发 M B/L ──→ NVOCC（你）
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                    签发 H B/L（合并）     签发 H B/L（直单）
                    给同行（货代）         给直客
                         │
                  ┌──────┴──────┐
                  │             │
              H B/L 1.1.1   H B/L 1.1.2
```

### 各层申报内容
| 角色 | 申报内容 |
|:----|:---------|
| **船公司** | M B/L + NVOCC 的 MPCI Party ID |
| **NVOCC（你）** | H B/L（合并）+ 标记子单数量 + 同行的 MPCI Party ID |
| **同行（Sub Co-loader）** | 底层 H B/L + 最终收货人信息 |

### 委托选项 (6.1.3.2)
- NVOCC 可代同行申报底层 H B/L
- 同行也可代 NVOCC 申报合并 H B/L

> 参考章节：§6.1
"""

    def _answer_consolidation_en(self, context: str) -> str:
        return """For consolidation or co-loading, every B/L layer needs to be linked so NAIC can trace the cargo chain.

Practical handling:

1. The shipping line files the Master B/L and identifies the NVOCC or relevant party.
2. The Master Co-loader files its consolidated B/L and identifies the expected lower-layer filer.
3. The Sub Co-loader files the lower House B/L with final shipper, consignee, and cargo details.
4. Parties should exchange MPCI Party IDs so parent and child filings can be linked.

If you do not actually issue a B/L at your layer, do not create a fake B/L number just for MPCI. Coordinate the correct Party IDs, parent B/L, child B/Ls, and filing responsibility instead."""

    def _answer_forwarder_child_cargo(self, context: str) -> str:
        return """先确认你是否实际签发自己这一层的提单，这是决定申报方式的关键。

## 你应该怎么做

### 1. 如果你不签发自己的 House B/L 或 Co-loader B/L
不要为了 MPCI 单独生成一个“你的提单号”。

你这一层如果没有实际签发提单，就不应该虚拟造一个 B/L 来申报。应由实际签发提单的一方申报他们签发的 B/L，并在链路中正确引用上层/下层关系。

你需要做的是协调资料：
- 向上层提供你的 MPCI Party ID，方便上层在它的 consolidated bill 中标明下一层责任方
- 向下层确认他们各自的 House B/L 号码和 MPCI Party ID
- 确认谁负责提交下层 House B/L：下层自己提交，或由你代他们提交

### 2. 如果你会对上层签发一张自己的 HBL / Co-loader B/L
那你就需要用你实际签发的这张 B/L 申报。

这张 B/L 应标记为 consolidation，因为后面还会有下层 House B/L 跟随。你需要在申报中体现：
- 你的 B/L 号码
- 上层 parent B/L 号码
- 上层的 MPCI Party ID
- 下层 expected filer 的 MPCI Party ID
- 下层 house bill 数量

下层再提交他们签发的 House B/L，并引用你的 B/L 作为 parent。

### 3. 如果你要替下层申报
可以代下层提交，但不要把下层的 B/L 变成你的 B/L。

代申报时应体现你是在 behalf of 下层提交，并使用下层作为这些 B/L 的 issuer。这样责任链才不会错。

## 简单判断

| 实际情况 | 你是否要生成自己的提单号 | 申报方式 |
|---|---:|---|
| 你没有签发任何 B/L，只是协调下层货物 | 不要生成 | 协调 Party ID、B/L 号和申报责任 |
| 你签发一张给上层的 HBL / Co-loader B/L | 需要，用实际 B/L 号 | 作为 consolidated bill 申报 |
| 你代下层提交他们的 HBL | 不生成你的 B/L 号 | 用下层 B/L，issuer 仍是下层 |

所以，你的问题里“下层会给我货物，但不需要我生成我的提单号”，更像是第一种或第三种：不要凭空生成你的提单号。重点是确认下层是否自己申报，还是你代他们申报；以及上层是否需要你的 MPCI Party ID 来链接这一层。"""

    def _answer_dnl(self, context: str) -> str:
        return """根据 MPCI 业务规范第 4.5 节和第 6.1.4.2 节：

## Do Not Load（DNL）影响规则

| 场景 | 影响 | 其他子单 |
|:----|:-----|:---------|
| **DNL 在 House B/L 层级** | ❌ **级联上升到 Master B/L**，两者都 DNL | ✅ **不受影响**，可移除有问题的子单后重新合并 |
| **DNL 在 Master B/L 层级** | ❌ **级联下传到所有 House B/L**，整票扣留 | 全部受影响 |

### 收到 DNL 后操作
1. 立即停止装船
2. 排查问题原因（安全风险、文件问题、法律违规）
3. 如果是 House B/L 的问题：移除该 House，剩下的重新合并到新 Master B/L
4. 重新申报

> 参考章节：§4.5, §6.1.4.2
"""

    def _answer_dnl_en(self, context: str) -> str:
        return """If one House B/L receives DNL, that issue affects the related Master B/L, but the other House B/Ls under the same master are not automatically treated as DNL.

What you should do:

1. Do not load the cargo covered by the DNL House B/L.
2. Identify and remove the problematic House B/L from the consolidation.
3. Re-consolidate or update the remaining cargo under a valid Master B/L structure.
4. Resubmit or update the affected filings as needed.

If the DNL is at Master B/L level, the impact is broader and can affect all House B/Ls under that Master."""

    def _answer_rfi(self, context: str) -> str:
        return """根据 MPCI 业务规范第 4.5 节和第 6.1.4.3 节：

## Request for Information (RFI)

### 含义
NAIC 认为提交的信息不完整、不准确或需要额外文件（如发票、原产地证、装箱单）。

### RFI 在不同层级的影响

| RFI 位置 | 影响 |
|:---------|:-----|
| **Master B/L 层** | ❌ **不级联**到 House B/L。House 可以收到 ACT，但 Master 在 RFI 解决前不能装船 |
| **House B/L 层** | Master B/L **保持 Pending**，直到 RFI 被解决。船公司不会收到明确通知 |

### 处理方式
1. 提交更新版本包含所需信息
2. 或通过附件服务上传所需文件
3. ⏰ **200 天内未处理 → Filing Expiry (EXP)**

> 参考章节：§4.5, §6.1.4.3
"""

    def _answer_rfi_en(self, context: str) -> str:
        return """RFI means Request for Information. It means NAIC needs additional or corrected information before the filing can be cleared.

Practical handling:

1. Check which B/L level received the RFI: Master or House.
2. Collect the missing data or requested supporting document.
3. Submit an updated filing or attachment as required.
4. Do not assume the shipment is cleared until the RFI is resolved.

If a Master B/L is under RFI, House B/Ls may already have ACT, but the Master cannot be treated as loadable until the Master-level RFI is resolved."""

    def _answer_psf(self, context: str) -> str:
        return """PSF 表示 Pending Sub Filing，通常说明下层 House B/L 还没有完成或没有正确关联。

你应该先联系缺失的 Sub Co-loader 或下层货代，确认他们是否已经提交 House B/L，并核对 parent B/L、Party ID 和提单号是否一致。下层补齐或修正后，上层状态才有机会解除 pending。"""

    def _answer_psf_en(self, context: str) -> str:
        return """PSF means Pending Sub Filing. It usually indicates that a lower-layer House B/L is missing, not yet filed, or not correctly linked.

What you should do:

1. Contact the relevant sub co-loader or lower-layer forwarder.
2. Ask them to file the missing House B/L or correct the existing filing.
3. Check that the parent B/L number, child B/L number, and MPCI Party IDs match.
4. Once the missing sub filing is completed and linked, the upper-level pending status can be cleared.

If the shipping line receives PSF because a sub co-loader has not filed, the practical action is to chase the missing House B/L filing rather than changing the Master B/L blindly."""

    def _answer_party_id(self, context: str) -> str:
        return """根据 MPCI 业务规范第 5.3 节（MPCI Party ID）：

## MPCI Party ID

### 是什么
NAIC 分配给每个经济运营商（船公司、货代、NVOCC）的唯一标识符。

### 使用场景

| 场景 | 要求 |
|:----|:-----|
| **所有申报** | 申报方必须提供自己的 MPCI Party ID |
| **委托 - 本地→海外货代** | 海外货代需引用本地货代的 Party ID |
| **委托 - 船公司→船代** | 船代需引用船公司的 Party ID |
| **Consolidation/Co-loading** | 各方需提供链中相关方的 Party ID |

### 获取方式
- **货代/NVOCC**：在 NAIC 门户注册时获得 | **不公开列出**
- **船公司**：所有船公司的 Party ID 在 NAIC 门户公开可查

> 💡 **注意**：货代之间的 Party ID 必须在内部自行分享。NAIC 门户不会公开货代的 Party ID。

> 参考章节：§5.3
"""

    def _answer_party_id_en(self, context: str) -> str:
        return """MPCI Party ID is the unique identifier assigned to a party such as a shipping line, freight forwarder, or NVOCC.

How to use it:

| Scenario | Practical use |
|---|---|
| Own filing | Provide your own MPCI Party ID |
| Delegated filing | The delegated filer needs the delegating party's MPCI Party ID |
| Consolidation / co-loading | Parties exchange Party IDs so parent and child filings can be linked |

Freight forwarder Party IDs are not publicly listed for other forwarders to search. If another forwarder needs to file and link to you, you should share your Party ID with them directly through your business channel."""

    def _answer_update(self, context: str) -> str:
        return """根据 MPCI 业务规范第 6.2 节（Updating a Bill of Lading）：

## 提单更新规则

### 常见更新场景

| 场景 | 操作 |
|:----|:-----|
| **更正（错误/重新测量）** | 提交更新版本 |
| **背书（收货人变更）** | 提交新收货人的版本 |
| **船/航次变更** | 取消原单 + 重新提交，或更新同一提单 |
| **合并/拆并** | 船公司提交新 M B/L，货代提交更新引用新 M B/L |
| **响应 RFI** | 按要求提交更新版本 |
| **Switch Bill** | 使用相同或不同提单号提交，标记为 switch |
| **取消** | 提交取消请求 |
| **分单** | 参见 Split Bill 规则 |

### 关键规则
- 🔄 更新后会**重新触发风险评估**
- ✅ 第一版必须在装船前提交，更新可以在到港后提交
- ❌ 取消后的提单不可更新，需重新申报
- ❌ 同一实体的相同提单号不能同时有两个有效申报
- ℹ️ 最终状态必须是 ACT、ACW 或 DNL
- ⏰ RFI 或 PSF 必须解决
- ⌛ **更新超过 200 天**会被系统拒绝

> 参考章节：§6.2
"""

    def _answer_update_en(self, context: str) -> str:
        return """Yes, B/L updates can be submitted after the shipment arrives in UAE, but the first filing still has to be submitted before loading.

Common update scenarios include:

| Scenario | Handling |
|---|---|
| Correction or re-measurement | Submit an updated version |
| Consignee change / endorsement | Submit the updated consignee details |
| Vessel or voyage change | Update or cancel and resubmit as appropriate |
| RFI response | Submit the missing or corrected information |
| Switch Bill / Split Bill | Submit the corresponding update or new linked B/L |

An update can trigger reassessment, so make sure the changed fields are accurate and the current B/L status allows the update."""

    def _answer_split(self, context: str) -> str:
        return """根据 MPCI 业务规范第 6.2.3 节（Split Bill of Lading Handling）：

## 分单处理

### 船公司责任
船公司有两种选择：
1. **保留原单不变** + 为分出的货物提交新提单，引用原单
2. **更新原单**反映分拆 + 提交新提单引用更新后的原单

### 货代责任

**如果只影响 M B/L：**
- 货代提交更新版 House B/L，引用分拆后的 M B/L

**如果同时影响 M B/L 和 H B/L：**
- 保留原 H B/L + 提交新 H B/L（引用原 H B/L 和分拆后的 M B/L）
- 或更新原 H B/L + 提交新 H B/L

> 参考章节：§6.2.3
"""

    def _answer_split_en(self, context: str) -> str:
        return """For a Split Bill of Lading, keep the parent-child relationship clear.

The shipping line can either keep the original B/L and submit a new B/L for the split cargo, or update the original B/L and submit the new linked B/L.

If House B/Ls are affected, the freight forwarder should update the relevant House B/Ls or submit new House B/Ls that reference the correct split Master B/L. Do not leave the lower-layer filings linked to an outdated parent B/L."""

    def _answer_goods(self, context: str) -> str:
        return """根据 MPCI 业务规范第 5.1 节：

## 货物重量与包装申报

当有多个 HS Code 时，以下字段需按货物项目（goods item）拆分：

| 字段 | 是否按 HS Code 拆分 | 说明 |
|:----|:------------------:|:-----|
| **Goods Description** | ✅ 是 | 每个货物项目分别描述 |
| **Package Type/Quantity** | ✅ 是 | 每个货物项目的包装类型和数量 |
| **Goods Weight** | ✅ 是 | 每个货物项目的重量（含包装，不含集装箱皮重） |
| **Container Goods Placement** | ✅ 是 | 指定每个货物项目装入哪个集装箱 |

### 货物描述规范（附录 D）
- ❌ 禁止笼统描述（如"General Cargo"、"FAK"、"STC"）
- ✅ 需要具体清晰的描述（如"Hexagonal Aluminum Bicycle Nuts"）
- ✅ 用英文描述
- ❌ 禁止纯数字、纯特殊字符、不完整描述

> 参考章节：§5.1, §Appendix D
"""

    def _answer_goods_en(self, context: str) -> str:
        return """Do not declare the goods description as only "general cargo" if the shipper cannot provide exact commodity details.

Before filing, ask the shipper to provide:

| Data | Requirement |
|---|---|
| Goods description | Specific English commodity description |
| HS Code | HS Code for each goods item |
| Package details | Package type and quantity |
| Weight | Gross weight for each goods item |
| Container placement | Which goods are loaded in which container |

Vague descriptions such as "general cargo", "FAK", "STC", or overly broad commodity wording are not safe for MPCI filing. If details are missing, collect them first rather than submitting incomplete cargo data."""

    def _answer_roles(self, context: str) -> str:
        return """根据 MPCI 业务规范第 3.1 节（Filers and Their Roles）：

## 申报人角色及责任

| 角色 | 责任 |
|:----|:-----|
| **🚢 船公司 (Shipping Line)** | 拥有或运营船舶的实体。可直接对接 NAIC 或通过服务商 |
| **📋 船代 (Shipping Agent)** | 船公司的代表，可被委托承担责任或管理申报 |
| **📦 货代 (Freight Forwarder)** | 物流服务商，合并多个发货人的货物 |
| **📊 Master Co-loader** | consolidation 中的上层，管理整个合并货物 |
| **📎 Sub Co-loader** | consolidation 中的下层，提供货物给 Master Co-loader |

### 需申报的单证

| 角色 | 单证类型 |
|:----|:---------|
| **船公司** | Master B/L 或 Direct B/L |
| **货代** | House B/L |
| **Master Co-loader** | Co-loader B/L（货代角度的 Master B/L） |
| **Sub Co-loader** | House B/L |

### 委托规则
- 货代可委托其他货代（§4.6.1）
- 船公司可委托船代（§4.6.2）

> 参考章节：§3.1, §3.2
"""

    def _answer_roles_en(self, context: str) -> str:
        return """The filing responsibility depends on the role and the B/L level:

| Role | Typical filing |
|---|---|
| Shipping line | Master B/L or Direct B/L |
| Shipping agent | Filing or responsibility delegated by shipping line |
| Freight forwarder / NVOCC | House B/L |
| Master Co-loader | Consolidated upper-layer co-loader B/L |
| Sub Co-loader | Lower-layer House B/L |

The practical question is always: who issued the B/L, which parent B/L it links to, and who is responsible for submitting that layer."""

    def _answer_general(self, query: str, context: str) -> str:
        """Generic answer when no specific pattern matches."""
        return f"""暂时无法判断“{query}”对应哪一个 MPCI 申报问题。

请补充一个更具体的业务场景，例如：
- 你是船公司、货代、NVOCC，还是船代？
- 问题涉及 Master B/L、House B/L，还是 Direct B/L？
- 你要处理的是申报时限、收货人、HS Code、委托申报、Consolidation、DNL/RFI，还是提单更新？

如果你是在问某个系统字段或报错，请把字段名、状态码或完整提示发出来，我可以按具体场景帮你判断。"""


class RAGEngine:
    """Main RAG Engine that orchestrates retrieval and generation."""

    def __init__(self, llm_type: str = "auto"):
        self.llm = LLMBackend(model_type=llm_type)
        self.collection = None
        self._load_or_build_store()

    def _load_or_build_store(self):
        """Load existing vector store or build from scratch."""
        self.collection = vector_store.load_vector_store()
        if self.collection is None:
            print("Building vector store from PDF text...")
            from .knowledge_base import build_knowledge_base
            chunks = build_knowledge_base()
            self.collection = vector_store.build_vector_store(chunks)

    def query(
        self,
        question: str,
        history: List[Dict] = None,
        top_k: int = 5
    ) -> Dict:
        """
        Answer a question using RAG.

        Args:
            question: User's question
            history: Conversation history
            top_k: Number of context chunks to retrieve

        Returns:
            Dict with 'answer', 'sources', 'confidence'
        """
        if self.collection is None:
            return {
                "answer": "知识库还未构建。请先运行知识库构建流程。",
                "sources": [],
                "confidence": 0
            }

        # Step 1: Retrieve relevant context
        retrieved = vector_store.search_vector_store(
            self.collection, question, k=top_k
        )
        retrieved = self._ensure_required_context(question, retrieved, top_k)

        if not retrieved:
            return {
                "answer": "暂时无法判断这个问题对应的 MPCI 申报场景。请补充你的角色、提单类型，以及你正在处理的动作或系统提示。",
                "sources": [],
                "confidence": 0
            }

        # Step 2: Build prompt with context
        prompt = build_prompt(question, retrieved, history)

        # Step 3: Generate answer
        answer = self.llm.generate(prompt)

        # Step 4: Format sources
        sources = []
        seen = set()
        for r in retrieved:
            key = f"{r['section_num']} {r['title']}"
            if key not in seen and r['score'] > 0.3:
                seen.add(key)
                sources.append({
                    "title": r["title"],
                    "section_num": r["section_num"],
                    "page_ref": r.get("page_ref", ""),
                    "relevance": round(r["score"], 3)
                })

        confidence = retrieved[0]["score"] if retrieved else 0

        return {
            "answer": answer,
            "sources": sources[:5],
            "confidence": round(confidence, 3)
        }

    def _ensure_required_context(
        self,
        question: str,
        retrieved: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """Add authoritative sections for known business topics if retrieval missed them."""
        sections = required_sections(question)
        if not sections:
            return retrieved

        present = {r.get("section_num") for r in retrieved}
        missing = [section for section in sections if section not in present]
        if not missing:
            return retrieved

        required_chunks = vector_store.get_chunks_by_sections(self.collection, missing)
        if not required_chunks:
            return retrieved

        merged = {}
        for item in required_chunks + retrieved:
            key = f"{item.get('section_num', '')}|{item.get('title', '')}"
            if key not in merged or item.get("score", 0) > merged[key].get("score", 0):
                merged[key] = item

        return sorted(
            merged.values(),
            key=lambda item: item.get("score", 0),
            reverse=True
        )[:top_k]
