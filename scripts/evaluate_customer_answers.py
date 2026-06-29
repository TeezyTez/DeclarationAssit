"""
Run customer-style questions through the local MPCI service or RAG engine and
apply lightweight answer quality checks.

Usage:
    python scripts/evaluate_customer_answers.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mpci_qa.rag_engine import RAGEngine


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            import os
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def mostly_english(text: str) -> bool:
    sample = text[:500]
    letters = sum(1 for char in sample if char.isascii() and char.isalpha())
    cjk = sum(1 for char in sample if "\u4e00" <= char <= "\u9fff")
    return letters > max(30, cjk * 2)


def main() -> int:
    load_env_file()
    cases = json.loads((ROOT / "tests" / "customer_questions.json").read_text(encoding="utf-8"))
    engine = RAGEngine(llm_type="auto")

    failures = []
    for case in cases:
        result = engine.query(case["question"])
        answer = result["answer"]
        lower = answer.lower()

        checks = []
        if case["language"] == "en":
            checks.append(("language_en", mostly_english(answer)))
        else:
            checks.append(("language_zh", has_cjk(answer)))

        must_terms = [term.lower() for term in case.get("must_contain_any", [])]
        checks.append(("must_contain_any", any(term in lower for term in must_terms)))

        bad_terms = [term.lower() for term in case.get("bad_terms", [])]
        checks.append(("no_bad_terms", not any(term in lower for term in bad_terms)))

        ok = all(value for _, value in checks)
        status = "PASS" if ok else "FAIL"
        print(f"{status} {case['id']}")
        print(answer[:500].replace("\n", " "))
        print()

        if not ok:
            failures.append({
                "case": case,
                "checks": checks,
                "answer": answer,
                "sources": result.get("sources", []),
            })

    if failures:
        print("Failures:")
        for failure in failures:
            print(f"- {failure['case']['id']}: {failure['checks']}")
            print(f"  sources: {[(s.get('section_num'), s.get('title')) for s in failure['sources']]}")
        return 1

    print(f"All customer-answer checks passed: {len(cases)}/{len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
