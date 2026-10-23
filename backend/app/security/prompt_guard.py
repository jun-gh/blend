"""Prompt Injection Guard with Sub-0.5ms Instant Quarantining and Boundary Escaping."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass


@dataclass
class PromptGuardResult:
    """Evaluation result from Prompt Injection Guard."""

    is_quarantined: bool
    reason: str | None = None
    matched_pattern: str | None = None
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Pre-compiled High-Performance Detection Patterns
# ---------------------------------------------------------------------------

# 1. System instruction override & rule bypass
_INSTRUCTION_OVERRIDE_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above|system)\s+(instructions|prompts|rules|commands)\b"),
    re.compile(r"(?i)\bdisregard\s+(all\s+)?(previous|prior|above|system)\s+(instructions|rules|prompts)\b"),
    re.compile(r"(?i)\bforget\s+(all\s+)?(previous|prior|system)\s+(instructions|rules|context)\b"),
    re.compile(r"(?i)\bstop\s+being\s+(a\s+)?(blend|helpful|assistant)\b"),
    re.compile(r"(?i)\bnew\s+system\s+(prompt|directive|instruction)\s*:\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(an?\s+)?(unfiltered|unrestricted|evil|dan|jailbreak)\b"),
]

# 2. Adversarial Persona / Jailbreak modes
_JAILBREAK_PATTERNS = [
    re.compile(r"(?i)\b(dan|jailbreak|developer|unlimited)\s+mode\s+(enabled|activated|engaged|on)\b"),
    re.compile(r"(?i)\bpretend\s+you\s+(have\s+no\s+rules|are\s+unfiltered|can\s+do\s+anything)\b"),
    re.compile(r"(?i)\balways\s+say\s+yes\s+to\s+everything\b"),
    re.compile(r"(?i)\boperate\s+without\s+(any\s+)?(filters|constraints|guardrails|safety)\b"),
]

# 3. Delimiter Injection & Prompt Boundary Escapes
_DELIMITER_ESCAPE_PATTERNS = [
    re.compile(r"</user_ticket_content>", re.IGNORECASE),
    re.compile(r"</context_documents>", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]|\[/SYSTEM\]|\[INST\]|\[/INST\]", re.IGNORECASE),
]

# 4. System Instruction Leaking / Extraction attacks
_SYSTEM_PROMPT_EXTRACTION_PATTERNS = [
    re.compile(r"(?i)\b(repeat|print|show|output|dump)\s+(all\s+)?(system\s+)?(instructions|prompts|rules|system\s+message)\b.*?\b(above|verbatim|word\s+for\s+word)\b"),
    re.compile(r"(?i)\bwhat\s+is\s+your\s+((original|hidden|initial|system)\s+)+(prompt|instruction|rules)\b"),
    re.compile(r"(?i)\bwhat\s+(were\s+you\s+told|are\s+your\s+rules|are\s+your\s+instructions)\s+at\s+the\s+beginning\b"),
]


def check_prompt_injection(query: str) -> PromptGuardResult:
    """Inspect query for adversarial prompt injection in sub-millisecond time.

    Quarantines malicious input instantly to protect LLM context windows
    and eliminate unnecessary model API costs.
    """
    t0 = time.perf_counter()
    if not query:
        return PromptGuardResult(is_quarantined=False, latency_ms=0.0)

    # 1. Delimiter boundary escape check
    for pat in _DELIMITER_ESCAPE_PATTERNS:
        match = pat.search(query)
        if match:
            latency = (time.perf_counter() - t0) * 1000
            return PromptGuardResult(
                is_quarantined=True,
                reason="Delimiter or prompt boundary injection attempt detected.",
                matched_pattern=match.group(0),
                latency_ms=round(latency, 3),
            )

    # 2. Instruction override check
    for pat in _INSTRUCTION_OVERRIDE_PATTERNS:
        match = pat.search(query)
        if match:
            latency = (time.perf_counter() - t0) * 1000
            return PromptGuardResult(
                is_quarantined=True,
                reason="System instruction override or jailbreak command detected.",
                matched_pattern=match.group(0),
                latency_ms=round(latency, 3),
            )

    # 3. Jailbreak persona check
    for pat in _JAILBREAK_PATTERNS:
        match = pat.search(query)
        if match:
            latency = (time.perf_counter() - t0) * 1000
            return PromptGuardResult(
                is_quarantined=True,
                reason="Adversarial persona / jailbreak mode detected.",
                matched_pattern=match.group(0),
                latency_ms=round(latency, 3),
            )

    # 4. System prompt extraction check
    for pat in _SYSTEM_PROMPT_EXTRACTION_PATTERNS:
        match = pat.search(query)
        if match:
            latency = (time.perf_counter() - t0) * 1000
            return PromptGuardResult(
                is_quarantined=True,
                reason="System prompt extraction / leaking attack detected.",
                matched_pattern=match.group(0),
                latency_ms=round(latency, 3),
            )

    latency = (time.perf_counter() - t0) * 1000
    return PromptGuardResult(is_quarantined=False, latency_ms=round(latency, 3))


def sanitize_user_input(text: str) -> str:
    """Escape XML boundary tags in untrusted user text before embedding into prompt."""
    if not text:
        return ""
    sanitized = text.replace("</user_ticket_content>", "&lt;/user_ticket_content&gt;")
    sanitized = sanitized.replace("<user_ticket_content>", "&lt;user_ticket_content&gt;")
    sanitized = sanitized.replace("</context_documents>", "&lt;/context_documents&gt;")
    sanitized = sanitized.replace("<context_documents>", "&lt;context_documents&gt;")
    return sanitized
