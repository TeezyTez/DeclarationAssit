"""
Generate a Markdown evaluation report for retrieval and customer-answer checks.

Usage:
    python scripts/generate_eval_report.py
    python scripts/generate_eval_report.py --output docs/eval_report.md
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mpci_qa import vector_store
from mpci_qa.rag_engine import RAGEngine


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def mostly_english(text: str) -> bool:
    sample = text[:500]
    letters = sum(1 for char in sample if char.isascii() and char.isalpha())
    cjk = sum(1 for char in sample if "\u4e00" <= char <= "\u9fff")
    return letters > max(30, cjk * 2)


def compact(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def evaluate_retrieval() -> tuple[list[dict], int]:
    cases = json.loads((ROOT / "tests" / "eval_questions.json").read_text(encoding="utf-8"))
    collection = vector_store.load_vector_store()
    if collection is None:
        raise RuntimeError("Vector store not found. Build it with: python -m mpci_qa.vector_store")

    rows = []
    passed = 0
    for case in cases:
        results = vector_store.search_vector_store(collection, case["question"], k=5)
        found_sections = [r["section_num"] for r in results]
        ok = any(section in found_sections for section in case["expected_sections"])
        passed += int(ok)
        rows.append({
            "id": case["id"],
            "question": case["question"],
            "expected": case["expected_sections"],
            "found": found_sections,
            "ok": ok,
        })
    return rows, passed


def evaluate_customer_answers() -> tuple[list[dict], int]:
    cases = json.loads((ROOT / "tests" / "customer_questions.json").read_text(encoding="utf-8"))
    engine = RAGEngine(llm_type="auto")

    rows = []
    passed = 0
    for case in cases:
        result = engine.query(case["question"])
        answer = result["answer"]
        lower = answer.lower()

        checks = {}
        if case["language"] == "en":
            checks["language"] = mostly_english(answer)
        else:
            checks["language"] = has_cjk(answer)

        must_terms = [term.lower() for term in case.get("must_contain_any", [])]
        checks["required_content"] = any(term in lower for term in must_terms)

        bad_terms = [term.lower() for term in case.get("bad_terms", [])]
        checks["no_reference_leakage"] = not any(term in lower for term in bad_terms)

        ok = all(checks.values())
        passed += int(ok)
        rows.append({
            "id": case["id"],
            "question": case["question"],
            "ok": ok,
            "checks": checks,
            "answer_preview": compact(answer),
            "sources": [s.get("section_num", "") for s in result.get("sources", [])],
        })
    return rows, passed


def render_report(
    retrieval_rows: list[dict],
    retrieval_passed: int,
    answer_rows: list[dict],
    answer_passed: int,
) -> str:
    retrieval_total = len(retrieval_rows)
    answer_total = len(answer_rows)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# MPCI QA Evaluation Report",
        "",
        f"Generated at: {timestamp}",
        "",
        "## Summary",
        "",
        f"- Retrieval hit rate: {retrieval_passed}/{retrieval_total}",
        f"- Customer-answer pass rate: {answer_passed}/{answer_total}",
        "",
        "## Retrieval Cases",
        "",
        "| Status | ID | Expected Sections | Retrieved Sections | Question |",
        "|---|---|---|---|---|",
    ]

    for row in retrieval_rows:
        status = "PASS" if row["ok"] else "FAIL"
        lines.append(
            f"| {status} | `{row['id']}` | {', '.join(row['expected'])} | "
            f"{', '.join(row['found'])} | {row['question']} |"
        )

    lines.extend([
        "",
        "## Customer Answer Cases",
        "",
        "| Status | ID | Checks | Sources | Answer Preview |",
        "|---|---|---|---|---|",
    ])

    for row in answer_rows:
        status = "PASS" if row["ok"] else "FAIL"
        checks = ", ".join(f"{name}={value}" for name, value in row["checks"].items())
        sources = ", ".join(row["sources"])
        preview = row["answer_preview"].replace("|", "\\|")
        lines.append(f"| {status} | `{row['id']}` | {checks} | {sources} | {preview} |")

    lines.extend([
        "",
        "## Notes",
        "",
        "- Retrieval passes when at least one expected manual section appears in the top results.",
        "- Customer-answer checks are lightweight guardrails, not a substitute for human review.",
        "- The report is meant to make RAG behavior visible during portfolio review and regression testing.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/eval_report.md")
    args = parser.parse_args()

    load_env_file()
    retrieval_rows, retrieval_passed = evaluate_retrieval()
    answer_rows, answer_passed = evaluate_customer_answers()
    report = render_report(retrieval_rows, retrieval_passed, answer_rows, answer_passed)

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Retrieval: {retrieval_passed}/{len(retrieval_rows)}")
    print(f"Customer answers: {answer_passed}/{len(answer_rows)}")
    return 0 if retrieval_passed == len(retrieval_rows) and answer_passed == len(answer_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
