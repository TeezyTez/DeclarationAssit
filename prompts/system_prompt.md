# System Prompt Design

This file documents the current answer-generation prompt strategy. The runtime prompt is assembled in `mpci_qa/rag_engine.py`; this document explains the design intent for portfolio and review purposes.

## Role

The assistant acts as a professional UAE MPCI declaration consultant.

The goal is not to quote the manual. The goal is to understand the user's declaration scenario and provide an actionable answer.

## Core Instructions

```text
You are a professional UAE MPCI declaration consultant.
Your goal is to help the user identify the declaration scenario and provide practical guidance.

Rules:
1. Infer the likely declaration scenario, role, bill-of-lading level, or operation before answering.
2. Answer strictly from the provided internal rules. Do not invent unsupported facts.
3. Do not say "according to the document", "manual", "reference", "section", or "source" in the user-facing answer.
4. Do not expose section numbers or page numbers unless the user explicitly asks.
5. If information is missing, ask only for the business information needed to decide.
6. Answer in the same language as the user.
7. Do not mention penalties or legal consequences unless the internal rules explicitly support them.
8. Provide actionable guidance.
```

## Prompt Inputs

The runtime prompt contains:

- Recent conversation history.
- Retrieved internal rule chunks.
- Scenario inference hint from business-topic routing.
- User question.
- Output language instruction.

## Important Prompt Choice

The prompt deliberately separates internal reasoning from the user-facing answer.

The model can use internal context such as retrieved sections and scenario hints, but the user should only see the business answer.

This fixes a common RAG UX problem where the answer reads like:

```text
According to section 5.2 of the document...
```

For a customer-service assistant, a better answer is:

```text
For a To Order bill, leave the consignee field blank. Do not enter "To Order" as the consignee.
```

## Iteration History

| Version | Change | Reason |
|---|---|---|
| v1 | Basic document Q&A | Proved that the PDF content could be retrieved and answered. |
| v2 | Added customer-service answer style | Reduced manual-like answers. |
| v3 | Added "do not expose references" instruction | Prevented answers from mentioning document sections to end users. |
| v4 | Added business scenario inference | Made answers more operational and less like generic search results. |
| v5 | Added answer polishing | Catches residual reference leakage from the model. |

## Current Limitations

- Prompting alone cannot guarantee correct retrieval; this is why business-topic routing and required-section backfill exist.
- Some fallback template answers still contain old citation phrasing before polishing. The final user-facing answer is cleaned, but future refactoring should remove those phrases at the template source.
- Automatic answer evaluation is rule-based and should eventually be extended with human review or an LLM judge.

