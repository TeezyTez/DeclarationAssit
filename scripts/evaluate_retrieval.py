"""
Evaluate whether retrieval returns the expected MPCI manual sections.

Usage:
    python scripts/evaluate_retrieval.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mpci_qa import vector_store


def main() -> int:
    eval_path = ROOT / "tests" / "eval_questions.json"
    cases = json.loads(eval_path.read_text(encoding="utf-8"))

    collection = vector_store.load_vector_store()
    if collection is None:
        print("Vector store not found. Build it with: python -m mpci_qa.vector_store")
        return 2

    passed = 0
    failures = []

    for case in cases:
        results = vector_store.search_vector_store(collection, case["question"], k=5)
        found_sections = [r["section_num"] for r in results]
        expected = case["expected_sections"]
        ok = any(section in found_sections for section in expected)

        if ok:
            passed += 1
        else:
            failures.append((case, found_sections, results))

        status = "PASS" if ok else "FAIL"
        print(f"{status} {case['id']}: expected {expected}, got {found_sections}")

    total = len(cases)
    print(f"\nRetrieval score: {passed}/{total}")

    if failures:
        print("\nFailures:")
        for case, found_sections, results in failures:
            print(f"- {case['id']} {case['question']}")
            for r in results:
                print(f"  {r['score']:.3f} §{r['section_num']} {r['title']}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
