"""PII Redaction Engine with Algorithmic Scrubbing and Safe Token Mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def luhn_check(card_number: str) -> bool:
    """Validate a credit card number using the Luhn checksum algorithm."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    # Process from right to left (double every second digit starting from penultimate)
    reverse_digits = digits[::-1]
    for idx, d in enumerate(reverse_digits):
        if idx % 2 == 1:
            doubled = d * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += d

    return checksum % 10 == 0


@dataclass
class SafeTokenMap:
    """In-memory mapping between surrogate tokens and scrubbed original values."""

    tokens: dict[str, str] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def register(self, original: str, category: str) -> str:
        """Register an original string and return a unique deterministic surrogate token."""
        # Reuse existing surrogate if this identical value was already scrubbed
        for surrogate, val in self.tokens.items():
            if val == original and self.categories.get(surrogate) == category:
                return surrogate

        count = self._counters.get(category, 0) + 1
        self._counters[category] = count
        surrogate = f"[REDACTED_{category}_{count}]"
        self.tokens[surrogate] = original
        self.categories[surrogate] = category
        return surrogate

    def restore(
        self,
        text: str,
        allowed_categories: set[str] | None = None,
    ) -> str:
        """Restore surrogate tokens in text.

        Args:
            text: Text containing [REDACTED_...] surrogates.
            allowed_categories: Set of categories permitted to be restored.
                If None, only low-risk categories (EMAIL, PHONE) are restored;
                credentials (API_KEY, PASSWORD, CREDIT_CARD, SSN) remain masked.
        """
        if not self.tokens:
            return text

        if allowed_categories is None:
            # Conservative default: credentials stay masked
            allowed_categories = {"EMAIL", "PHONE"}

        result = text
        for surrogate, original in self.tokens.items():
            cat = self.categories.get(surrogate, "")
            if cat in allowed_categories and surrogate in result:
                result = result.replace(surrogate, original)
        return result

    @property
    def has_redactions(self) -> bool:
        return bool(self.tokens)


# ---------------------------------------------------------------------------
# Compiled Regex Patterns
# ---------------------------------------------------------------------------

# Credit card candidate pattern (13-19 digits with optional hyphens or spaces)
_CREDIT_CARD_REGEX = re.compile(
    r"\b(?:\d[ -]*?){13,19}\b"
)

# API Keys and Cloud Credentials
_API_KEY_PATTERNS = [
    # Google Gemini API key
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{30,45}\b"), "API_KEY"),
    # OpenAI secret key
    (re.compile(r"\bsk-[a-zA-Z0-9_\-]{20,}\b"), "API_KEY"),
    # GitHub personal access tokens
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"), "API_KEY"),
    # AWS access key ID
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "API_KEY"),
    # JWT tokens (Header.Payload.Signature)
    (re.compile(r"\beyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\b"), "JWT"),
]

# Password or secret assignments: password="xyz", api_key='abc'
_SECRET_ASSIGNMENT_REGEX = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|passwd|auth[_-]?token|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.@#$%^&*!]{6,})['\"]?"
)

# Email address (RFC 5322)
_EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# US Social Security Number
_SSN_REGEX = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b"
)

# Phone numbers (E.164, US domestic, international with country code)
_PHONE_REGEX = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)


def scrub_pii(text: str) -> tuple[str, SafeTokenMap]:
    """Scrub PII, credentials, passwords, and sensitive data from *text*.

    Returns:
        tuple of (sanitized_text, SafeTokenMap)
    """
    if not text:
        return text, SafeTokenMap()

    token_map = SafeTokenMap()
    sanitized = text

    # 1. API Keys & Cloud tokens
    for pattern, category in _API_KEY_PATTERNS:
        for match in pattern.finditer(sanitized):
            raw = match.group(0)
            surrogate = token_map.register(raw, category)
            sanitized = sanitized.replace(raw, surrogate)

    # 2. Key=Value Secret & Password assignments
    def _mask_secret(m: re.Match) -> str:
        key_name = m.group(1)
        secret_val = m.group(2)
        surrogate = token_map.register(secret_val, "PASSWORD")
        # Preserve the assignment structure, only mask the value
        return f"{key_name}={surrogate}"

    sanitized = _SECRET_ASSIGNMENT_REGEX.sub(_mask_secret, sanitized)

    # 3. Credit Cards (with Luhn Check verification)
    for match in list(_CREDIT_CARD_REGEX.finditer(sanitized)):
        candidate = match.group(0)
        digits_only = re.sub(r"\D", "", candidate)
        if 13 <= len(digits_only) <= 19 and luhn_check(digits_only):
            surrogate = token_map.register(candidate, "CREDIT_CARD")
            sanitized = sanitized.replace(candidate, surrogate)

    # 4. Social Security Numbers
    for match in _SSN_REGEX.finditer(sanitized):
        raw = match.group(0)
        surrogate = token_map.register(raw, "SSN")
        sanitized = sanitized.replace(raw, surrogate)

    # 5. Email Addresses
    for match in _EMAIL_REGEX.finditer(sanitized):
        raw = match.group(0)
        surrogate = token_map.register(raw, "EMAIL")
        sanitized = sanitized.replace(raw, surrogate)

    # 6. Phone Numbers
    for match in _PHONE_REGEX.finditer(sanitized):
        raw = match.group(0)
        # Avoid redacting simple short numbers or dates
        if len(re.sub(r"\D", "", raw)) >= 10:
            surrogate = token_map.register(raw, "PHONE")
            sanitized = sanitized.replace(raw, surrogate)

    return sanitized, token_map
