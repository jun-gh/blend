"""Conversational Intent Detection.

Identifies chit-chat, greetings, gratitude, and meta-assistant questions
to bypass document retrieval and prevent false-positive citations.
"""

from __future__ import annotations

import re
from typing import Any

# Standalone conversational expressions (exact or regex match on normalized query)
_GREETING_PATTERNS = [
    re.compile(r"^(hi|hello|hey|heya|howdy|greetings|hola)\b", re.IGNORECASE),
    re.compile(r"^good\s+(morning|afternoon|evening|day|night)\b", re.IGNORECASE),
    re.compile(
        r"^how\s+(are\s+you|are\s+you\s+doing|is\s+it\s+going|are\s+things)( today)?(\b|\?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(how('?s|\s+is)|what('?s|\s+is))\s+(the\s+)?weather\b",
        re.IGNORECASE,
    ),
    re.compile(r"^what('?s|\s+is)\s+up(\b|\?)", re.IGNORECASE),
    re.compile(r"^how\s+do\s+you\s+do(\b|\?)", re.IGNORECASE),
]

_COURTESY_PATTERNS = [
    re.compile(
        r"^(thanks|thank\s+you|many\s+thanks|thx)((\s+so\s+much|\s+very\s+much|\s+a\s+lot)?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^(you('?re|\s+are)\s+welcome|no\s+problem|my\s+pleasure)\b", re.IGNORECASE),
    re.compile(
        r"^(bye|goodbye|see\s+you|see\s+ya|have\s+a\s+(good|great|nice)\s+day)\b",
        re.IGNORECASE,
    ),
]

_IDENTITY_PATTERNS = [
    re.compile(r"^(who|what)\s+(are\s+you|is\s+your\s+name|is\s+blend)(\b|\?)", re.IGNORECASE),
    re.compile(
        r"^what\s+(can\s+you\s+do|do\s+you\s+do|are\s+your\s+capabilities)(\b|\?)",
        re.IGNORECASE,
    ),
    re.compile(r"^help(\s+me)?(\b|\?)", re.IGNORECASE),
]

# Words that indicate the user wants to search documents, even if combined with a greeting
_DOCUMENT_DIRECTIVE_WORDS = {
    "document",
    "documents",
    "pdf",
    "file",
    "files",
    "paper",
    "resume",
    "cv",
    "contract",
    "search",
    "find",
    "summarize",
    "explain",
    "tell",
    "show",
    "extract",
    "according",
    "section",
    "page",
}


def is_conversational_query(query: str) -> bool:
    """Return True if the query is a greeting, polite pleasantry, or meta-question.

    Conversational queries do not require document retrieval and should not
    return source citations.
    """
    clean = query.strip()
    if not clean:
        return True

    # Strip surrounding quotes and whitespace
    clean = clean.strip("\"'").strip()

    # Normalize punctuation and tokenize
    words = re.findall(r"\b\w+\b", clean.lower())
    if not words:
        return True

    # If the user explicitly asks about documents or files, run retrieval
    if any(w in _DOCUMENT_DIRECTIVE_WORDS for w in words) and len(words) > 4:
        return False

    # Check for direct conversational regex matches
    # Long complex questions (> 8 words) are almost never purely conversational greetings
    if len(words) <= 8:
        for pat in _GREETING_PATTERNS:
            if pat.search(clean):
                return True
        for pat in _COURTESY_PATTERNS:
            if pat.search(clean):
                return True
        for pat in _IDENTITY_PATTERNS:
            if pat.search(clean):
                return True

    return False


_NO_CONTEXT_PATTERNS = [
    re.compile(r"do(?:es)?\s+not\s+contain", re.IGNORECASE),
    re.compile(
        r"not\s+(?:found|mentioned|stated|discussed|provided)\s+in\s+the\s+(?:provided\s+|context\s+)?document",
        re.IGNORECASE,
    ),
    re.compile(
        r"no\s+information\s+(?:regarding|about|on)?.*in\s+the\s+(?:provided\s+|context\s+)?document",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:provided\s+|context\s+)?documents?\s+(?:do(?:es)?\s+not|never)\s+(?:contain|mention|state|provide|have)",
        re.IGNORECASE,
    ),
    re.compile(
        r"cannot\s+(?:find|determine|answer).*based\s+on\s+the\s+(?:provided\s+)?document",
        re.IGNORECASE,
    ),
    re.compile(r"could\s+not\s+find\s+any\s+relevant\s+information", re.IGNORECASE),
    re.compile(
        r"insufficient\s+information\s+in\s+the\s+(?:provided\s+)?document",
        re.IGNORECASE,
    ),
    re.compile(r"no\s+relevant\s+context\s+found", re.IGNORECASE),
]


def is_no_context_answer(answer: str) -> bool:
    """Return True if answer states that documents/context lack information.

    When an answer contains phrases like 'documents do not contain', citations
    must be stripped to prevent false attribution of unrelated document chunks.
    """
    if not answer:
        return False
    return any(p.search(answer) for p in _NO_CONTEXT_PATTERNS)


def align_citations_with_answer(
    answer: str,
    context_chunks: list[Any],
) -> list[Any]:
    """Filter and align returned citations to those that directly support the generated answer.

    Eliminates irrelevant citations from other documents (e.g. Cover Letter when CV is cited)
    and non-supporting chunks from the cited document.
    """
    if not context_chunks or not answer.strip():
        return []

    # 1. Negative response suppression
    if is_no_context_answer(answer):
        return []

    # 2. Document-level alignment based on inline citations [Doc: <Title>]
    cited_docs = set(re.findall(r"\[Doc:\s*([^\]]+)\]", answer, re.IGNORECASE))
    eligible = context_chunks
    if cited_docs:
        cited_low = {d.strip().lower() for d in cited_docs}
        matched = [
            c
            for c in context_chunks
            if c.document_title.strip().lower() in cited_low
            or any(cd in c.document_title.strip().lower() for cd in cited_low)
        ]
        if matched:
            eligible = matched

    # 3. Fact & Entity Grounding Overlap
    clean_ans = re.sub(r"\[Doc:[^\]]+\]", "", answer, flags=re.IGNORECASE)
    ans_tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\@\.]+\b", clean_ans.lower()))

    filler = {
        "based", "on", "the", "provided", "documents", "document", "according",
        "to", "you", "your", "live", "lives", "stated", "mentioned", "notes",
        "shows", "here", "is", "are", "in", "at", "a", "an", "and", "or",
        "this", "that", "these", "those", "for", "with", "as", "by", "from",
        "about", "into", "through", "during", "before", "after", "above", "below",
        "up", "down", "out", "off", "over", "under", "again", "further", "then",
        "once", "there", "when", "where", "why", "how", "all", "any", "both",
        "each", "few", "more", "most", "other", "some", "such", "no", "nor",
        "not", "only", "own", "same", "so", "than", "too", "very", "s", "t",
        "can", "will", "just", "don", "should", "now",
    }
    key_tokens = {w for w in ans_tokens if w not in filler and len(w) > 1}

    if not key_tokens:
        return eligible[:1]

    # Score eligible chunks by overlap with key answer tokens
    scored: list[tuple[Any, float, set[str]]] = []
    for c in eligible:
        c_words = set(re.findall(r"\b[a-zA-Z0-9_\-\@\.]+\b", c.content.lower()))
        overlap = key_tokens.intersection(c_words)
        score = len(overlap) / len(key_tokens)
        scored.append((c, score, overlap))

    scored.sort(key=lambda x: (x[1], getattr(x[0], "score", 0.0)), reverse=True)

    top_support = scored[0][1] if scored else 0.0
    if top_support > 0:
        # Keep only chunks that actually contain supporting answer tokens
        # and whose support is within 60% of top support
        cutoff = max(0.20, top_support * 0.60)
        supported = [c for c, s, _ in scored if s >= cutoff and s > 0]
        if supported:
            return supported

    return [eligible[0]]


