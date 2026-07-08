from __future__ import annotations

from typing import Literal

ConsentClassification = Literal["ACCEPT", "DECLINE", "QUESTION", "AMBIGUOUS"]

VALID_CONSENT_CLASSIFICATIONS: set[str] = {"ACCEPT", "DECLINE", "QUESTION", "AMBIGUOUS"}
