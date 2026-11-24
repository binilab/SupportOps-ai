"""정책 문서를 청크로 나누고 BM25로 검색한다.

정책 Markdown 한 파일이 정책 하나이고, `## ` 소제목 단위로 잘라 청크를 만든다.
청크 ID는 `정책ID::번호` 형식이라 답변의 인용을 원문 위치까지 추적할 수 있다.
BM25는 키워드 기반 검색의 기준선이자, 하이브리드 검색의 한쪽 축이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

POLICY_ID_RE = re.compile(r"^정책 ID: `([^`]+)`$", re.MULTILINE)
# 한글·영문·숫자 연속 구간을 토큰으로 본다. 형태소 분석 없이 쓰는 단순 기준선이다.
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


@dataclass(frozen=True)
class PolicyDocument:
    """정책 Markdown 파일 하나."""

    policy_id: str
    source_path: str
    title: str
    text: str


@dataclass(frozen=True)
class PolicyChunk:
    """검색과 인용의 단위가 되는 정책 문서의 한 섹션."""

    chunk_id: str
    policy_id: str
    source_path: str
    title: str
    heading: str
    text: str

    @property
    def search_text(self) -> str:
        """검색에 쓰는 텍스트. 본문만으로는 맥락이 부족해 정책 제목과 소제목을 앞에 붙인다."""
        return " ".join((self.title, self.heading, self.text))


@dataclass(frozen=True)
class PolicyHit:
    """검색 결과 한 건. 정책 하나당 점수가 가장 높은 청크를 대표로 담는다."""

    policy_id: str
    chunk_id: str
    source_path: str
    score: float


def tokenize(text: str) -> list[str]:
    """문서와 질문에 같은 규칙(소문자화 + 토큰 추출)을 적용한다."""
    return TOKEN_RE.findall(text.casefold())


def load_policy_documents(policy_dir: Path, root: Path) -> list[PolicyDocument]:
    """정책 폴더의 Markdown 파일을 읽는다.

    파일마다 `# 제목`과 `정책 ID:` 줄이 반드시 있어야 하며, 없으면 오류를 낸다.
    source_path는 저장소 루트 기준 상대 경로로 저장해 인용에 그대로 쓴다.
    """
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
    """문서를 `## ` 소제목 단위로 나눈다.

    첫 소제목 앞의 본문은 "개요" 섹션이 된다. 청크 번호는 문서 안에서 01부터 매겨서,
    정책 파일이 추가돼도 다른 정책의 청크 ID는 바뀌지 않는다.
    """
    chunks: list[PolicyChunk] = []
    for document in documents:
        sections: list[tuple[str, list[str]]] = []
        heading = "개요"
        body: list[str] = []
        # 첫 줄(# 제목)은 건너뛰고, "정책 ID:" 줄은 본문에서 뺀다.
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
    """정책 문서를 읽고 바로 청크로 나눈다."""
    return chunk_policy_documents(load_policy_documents(policy_dir, root))


class BM25PolicyIndex:
    """청크 단위 BM25 인덱스. 결과는 정책 단위로 묶어서 돌려준다."""

    def __init__(self, chunks: list[PolicyChunk]) -> None:
        if not chunks:
            raise ValueError("At least one policy chunk is required")
        self.chunks = chunks
        self.model = BM25Okapi([tokenize(chunk.search_text) for chunk in chunks])

    def search(self, query: str, k: int = 5) -> list[PolicyHit]:
        """질문과 가장 관련 있는 정책 k개를 찾는다.

        모든 청크에 점수를 매긴 뒤 정책마다 최고 점수 청크 하나만 남긴다.
        평가 기준이 "올바른 정책을 찾았는가"라서 같은 정책의 청크가 상위권을 독차지하지 않게 한다.
        """
        if k < 1:
            raise ValueError("k must be positive")
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.model.get_scores(tokens)
        best_by_policy: dict[str, PolicyHit] = {}
        for chunk, score in zip(self.chunks, scores, strict=True):
            # 겹치는 단어가 하나도 없는 청크(점수 0 이하)는 후보에서 뺀다.
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
        # 점수가 같으면 정책 ID 순으로 정렬해 실행할 때마다 결과가 같게 한다.
        return sorted(best_by_policy.values(), key=lambda hit: (-hit.score, hit.policy_id))[:k]
