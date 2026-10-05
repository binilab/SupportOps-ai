"""Phase 1 policy chunks and a minimal BM25 retrieval baseline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

POLICY_ID_RE = re.compile(r"^정책 ID: `([^`]+)`$", re.MULTILINE)
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


@dataclass(frozen=True)
class PolicyDocument:
    policy_id: str
    source_path: str
    title: str
    text: str


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    policy_id: str
    source_path: str
    title: str
    heading: str
    text: str

    @property
    def search_text(self) -> str:
        return " ".join((self.title, self.heading, self.text))


@dataclass(frozen=True)
class PolicyHit:
    policy_id: str
    chunk_id: str
    source_path: str
    score: float


def tokenize(text: str) -> list[str]:
    """Apply the same simple word normalization to documents and queries."""
    return TOKEN_RE.findall(text.casefold())


def load_policy_documents(policy_dir: Path, root: Path) -> list[PolicyDocument]:
    """Read policy Markdown files as source-traceable documents."""
    documents: list[PolicyDocument] = []
    for path in sorted(policy_dir.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or not lines[0].startswith("# "):
            raise ValueError(f"Missing policy title: {path}")
        source = "\n".join(lines)
        match = POLICY_ID_RE.search(source)
        if match is None:
            raise ValueError(f"Missing policy ID: {path}")
        policy_id = match.group(1)
        title = lines[0][2:].strip()
        source_path = path.relative_to(root).as_posix()
        documents.append(PolicyDocument(policy_id, source_path, title, source))
    if not documents:
        raise ValueError(f"No policy documents found in {policy_dir}")
    return documents


def chunk_policy_documents(documents: list[PolicyDocument]) -> list[PolicyChunk]:
    """Split documents at level-two headings with stable per-document IDs."""
    chunks: list[PolicyChunk] = []
    for document in documents:
        sections: list[tuple[str, list[str]]] = []
        heading = "개요"
        body: list[str] = []
        for line in document.text.splitlines()[1:]:
            if line.startswith("## "):
                if any(item.strip() for item in body if not item.startswith("정책 ID:")):
                    sections.append((heading, body))
                heading, body = line[3:].strip(), []
            elif not line.startswith("정책 ID:"):
                body.append(line)
        if any(item.strip() for item in body):
            sections.append((heading, body))

        for number, (section_heading, section_lines) in enumerate(sections, start=1):
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{document.policy_id}::{number:02d}",
                    policy_id=document.policy_id,
                    source_path=document.source_path,
                    title=document.title,
                    heading=section_heading,
                    text="\n".join(section_lines).strip(),
                )
            )
    if not chunks:
        raise ValueError("No policy chunks found")
    return chunks


def load_policy_chunks(policy_dir: Path, root: Path) -> list[PolicyChunk]:
    """Load source documents and derive their searchable chunks."""
    return chunk_policy_documents(load_policy_documents(policy_dir, root))


class BM25PolicyIndex:
    def __init__(self, chunks: list[PolicyChunk]) -> None:
        if not chunks:
            raise ValueError("At least one policy chunk is required")
        self.chunks = chunks
        self.model = BM25Okapi([tokenize(chunk.search_text) for chunk in chunks])

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """Return the best matching chunk for each distinct policy ID."""
        if k < 1:
            raise ValueError("k must be positive")
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.model.get_scores(tokens)
        best_by_policy: dict[str, PolicyHit] = {}
        for chunk, score in zip(self.chunks, scores, strict=True):
            if score <= 0:
                continue
            candidate = PolicyHit(
                policy_id=chunk.policy_id,
                chunk_id=chunk.chunk_id,
                source_path=chunk.source_path,
                score=float(score),
            )
            previous = best_by_policy.get(chunk.policy_id)
            if previous is None or candidate.score > previous.score:
                best_by_policy[chunk.policy_id] = candidate
        return sorted(best_by_policy.values(), key=lambda hit: (-hit.score, hit.policy_id))[:k]
