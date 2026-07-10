from __future__ import annotations

"""Colombian street-type (vía) normalization.

Canonicalizes the common abbreviations used in RUNT / official addresses so that
address comparison and display are consistent:

    CL / CLL / CALLE            -> CALLE
    CR / CRA / KR / KRA / CARRERA -> CARRERA
    AV / AVE / AVENIDA          -> AVENIDA
    DG / DIAG / DIAGONAL        -> DIAGONAL
    TV / TR / TRANS / TRANSVERSAL -> TRANSVERSAL
"""

import re
import unicodedata


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(ch)
    )


# Canonical vía -> ordered set of accepted abbreviations. Longer/again-canonical
# spellings are listed too so the mapping is idempotent.
VIA_ALIASES: dict[str, tuple[str, ...]] = {
    "CALLE": ("CALLE", "CLL", "CLE", "CALL", "CL"),
    "CARRERA": ("CARRERA", "CRA", "KRA", "CARR", "CR", "KR"),
    "AVENIDA CARRERA": ("AVENIDA CARRERA", "AK"),
    "AVENIDA": ("AVENIDA", "AVDA", "AVEN", "AVE", "AV"),
    "DIAGONAL": ("DIAGONAL", "DIAG", "DGNL", "DG"),
    "TRANSVERSAL": ("TRANSVERSAL", "TRANSV", "TRANS", "TVL", "TV", "TR"),
    "CIRCULAR": ("CIRCULAR", "CIRC", "CQ"),
    "AUTOPISTA": ("AUTOPISTA", "AUTOP", "AUT"),
}

# Compile one anchored pattern per canonical target, matching any alias as a whole
# token with an optional trailing period (e.g. "CRA." or "Cra").
_VIA_PATTERNS: list[tuple[re.Pattern[str], str]] = []
for _canonical, _aliases in VIA_ALIASES.items():
    # Sort aliases by length desc so multi-word / longer aliases win first.
    _alt = "|".join(sorted((re.escape(a) for a in _aliases), key=len, reverse=True))
    _VIA_PATTERNS.append((re.compile(rf"(?<![A-Z0-9])(?:{_alt})\.?(?![A-Z0-9])"), _canonical))

# NUMERO markers -> "#": NO, NRO, NUM, NUMERO, N (as a standalone token before digits).
_NUMERO_PATTERN = re.compile(r"(?<![A-Z0-9])(?:NUMERO|NUMRO|NRO|NUM|NO|N)\.?(?=\s*#?\s*\d)")


def canonical_via(token: str) -> str | None:
    """Return the canonical vía for a single abbreviation token, or None."""
    key = _strip_accents((token or "").strip().upper()).rstrip(".")
    for canonical, aliases in VIA_ALIASES.items():
        if key in aliases:
            return canonical
    return None


def normalize_colombia_address(value: str | None) -> str:
    """Uppercase, de-accent, and canonicalize Colombian street types.

    The result is stable/idempotent: normalizing an already-normalized address
    returns the same string.
    """
    if not value:
        return ""
    text = _strip_accents(value.upper())
    # Standardize separators around numbers early: "N 12-24" style stays readable.
    text = re.sub(r"\s+", " ", text).strip()
    for pattern, canonical in _VIA_PATTERNS:
        text = pattern.sub(canonical, text)
    text = _NUMERO_PATTERN.sub("#", text)
    # Collapse duplicate hashes/spaces introduced by substitutions.
    text = re.sub(r"#\s*#", "#", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


__all__ = ["VIA_ALIASES", "canonical_via", "normalize_colombia_address"]
