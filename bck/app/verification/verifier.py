"""Conservative deterministic claim verification against grounded observations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

CLAIM_BOUNDARY = re.compile(r"(?<=[.!?;])\s+|\s+(?:and|but|while|whereas)\s+", re.IGNORECASE)
WORD_PATTERN = re.compile(r"[a-z0-9]+")
NON_EVIDENTIAL_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "in",
        "on",
        "at",
        "of",
        "to",
        "for",
        "from",
        "this",
        "that",
        "there",
        "appears",
        "appear",
        "scene",
        "image",
    }
)


class VerificationStatus(StrEnum):
    """Outcome of comparing candidate claims with grounded observations."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Verified answer plus an auditable record of accepted and rejected claims."""

    status: VerificationStatus
    verified_text: str
    supported_claims: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    abstained: bool
    abstention_reason: str | None


def verify_answer(
    candidate_answer: str, supporting_observations: list[str] | tuple[str, ...]
) -> VerificationResult:
    """Retain only candidate claims whose content is present in a grounded observation."""
    claims = _split_claims(candidate_answer)
    observations = tuple(item.strip() for item in supporting_observations if item.strip())
    supported = tuple(claim for claim in claims if _claim_is_supported(claim, observations))
    rejected = tuple(claim for claim in claims if claim not in supported)

    if not supported:
        return VerificationResult(
            status=VerificationStatus.REJECTED,
            verified_text="",
            supported_claims=(),
            rejected_claims=rejected,
            abstained=True,
            abstention_reason="No candidate claim was supported by grounded visual observations.",
        )

    status = (
        VerificationStatus.SUPPORTED if not rejected else VerificationStatus.PARTIALLY_SUPPORTED
    )
    verified_text = " ".join(_as_sentence(claim) for claim in supported)
    return VerificationResult(
        status=status,
        verified_text=verified_text,
        supported_claims=supported,
        rejected_claims=rejected,
        abstained=False,
        abstention_reason=None,
    )


def _split_claims(answer: str) -> tuple[str, ...]:
    """Split prose into atomic sentence and conjunction-delimited candidate claims."""
    return tuple(
        cleaned
        for part in CLAIM_BOUNDARY.split(answer.strip())
        if (cleaned := part.strip().strip("-• \t\r\n.!?;:"))
    )


def _claim_is_supported(claim: str, observations: tuple[str, ...]) -> bool:
    """Require every evidential claim term to occur in at least one observation."""
    claim_terms = _evidential_terms(claim)
    if not claim_terms:
        normalized_claim = " ".join(WORD_PATTERN.findall(claim.lower()))
        return any(
            normalized_claim == " ".join(WORD_PATTERN.findall(item.lower()))
            for item in observations
        )
    return any(claim_terms.issubset(_evidential_terms(item)) for item in observations)


def _evidential_terms(text: str) -> frozenset[str]:
    """Normalize a claim into content terms without deleting negation."""
    return frozenset(
        word for word in WORD_PATTERN.findall(text.lower()) if word not in NON_EVIDENTIAL_WORDS
    )


def _as_sentence(claim: str) -> str:
    """Normalize one accepted claim for user-facing sentence assembly."""
    sentence = claim[0].upper() + claim[1:] if claim else claim
    return sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."
