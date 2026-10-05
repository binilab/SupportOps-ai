"""Run the fixed Phase 1 policy-retrieval evaluation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supportops.lexical import BM25PolicyIndex, load_policy_chunks  # noqa: E402
from supportops.retrieval_eval import evaluate  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_dataset.jsonl"
POLICY_DIR = ROOT / "data" / "raw" / "policies"
def main() -> int:
    rows = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    index = BM25PolicyIndex(load_policy_chunks(POLICY_DIR, ROOT))
    result = evaluate(rows, index)
    result["gold_sha256"] = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()
    policy_digest = hashlib.sha256()
    for path in sorted(POLICY_DIR.glob("*.md")):
        policy_digest.update(path.name.encode("utf-8"))
        policy_digest.update(b"\0")
        policy_digest.update(path.read_bytes())
        policy_digest.update(b"\0")
    result["policy_corpus_sha256"] = policy_digest.hexdigest()
    result["python_version"] = sys.version.split()[0]
    result["numpy_version"] = importlib.metadata.version("numpy")
    result["tokenizer"] = "lowercase regex [가-힣A-Za-z0-9]+"
    result["bm25"] = f"rank-bm25 {importlib.metadata.version('rank-bm25')} BM25Okapi default parameters"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
