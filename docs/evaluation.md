# Evaluation

The project includes two lightweight evaluations: retrieval evaluation and customer-answer evaluation. The goal is to show that the system is not only able to call an LLM, but can be checked against expected business behavior.

## Retrieval Evaluation

Script:

```bash
python scripts/evaluate_retrieval.py
```

Dataset:

```text
tests/eval_questions.json
```

Each case contains:

- `question`: user-style question.
- `expected_sections`: manual sections that should appear in the retrieved results.
- `must_contain`: business terms that the relevant context should include.

The script loads the ChromaDB collection and checks whether at least one expected section is present in the top retrieved chunks.

Covered scenarios include:

- Filing timing
- To Order consignee handling
- HS Code and goods description
- HBL mandatory data
- Delegation
- Consolidation and co-loading
- DNL / RFI
- MPCI Party ID
- Bill of Lading update and split bill handling

## Customer Answer Evaluation

Script:

```bash
python scripts/evaluate_customer_answers.py
```

Dataset:

```text
tests/customer_questions.json
```

Each case checks:

- Output language: Chinese questions should receive Chinese answers, English questions should receive English answers.
- Required content: the answer should contain at least one expected business term.
- Forbidden content: the answer should not expose document/reference wording.

This is not a full automatic judge, but it catches practical failures such as:

- The model answers in the wrong language.
- The model says it cannot answer despite available rules.
- The answer leaks "reference section" or "according to the manual" language.
- The answer misses the key operational instruction.

## Report Generation

To generate a Markdown report:

```bash
python scripts/generate_eval_report.py
```

Default output:

```text
docs/eval_report.md
```

The report includes:

- Retrieval hit rate.
- Per-case retrieved sections.
- Customer-answer pass rate.
- Per-case quality checks.
- Sources returned by the RAG engine for debugging.

## What This Demonstrates

For a job portfolio, these tests demonstrate an AI engineering workflow:

- Build a RAG system.
- Identify failure modes.
- Add business-specific routing and retrieval repair.
- Evaluate retrieval and answer behavior with repeatable cases.
- Keep improving prompts and routing based on test failures.

This is closer to real AI product development than a one-off chatbot demo.

