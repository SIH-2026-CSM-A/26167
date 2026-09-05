"""Deterministic schema-constrained intent classification for geospatial queries."""

from __future__ import annotations

import re

from app.router.schemas import IntentClassification, TaskType

# Compiled regex patterns for deterministic task classification.
# Evaluation order:
# 1. Archive Search (Bonus capability)
# 2. Cross-Modal Fusion (Optical + SAR joint analysis)
# 3. Change-VQA (Bi-temporal comparative analysis)
# 4. Grounding (Referring expression segmentation / localization)
# 5. VQA (Default single-image visual question answering)

_ARCHIVE_SEARCH_PATTERN = re.compile(
    r"\b(archive|catalog)\b.*\b(search|find|retriev|query)\b|"
    r"\b(search|query|retriev|find)\b.*\b(archive|catalog)\b",
    re.IGNORECASE,
)

_FUSION_PATTERNS = [
    re.compile(r"\b(optical\s+and\s+sar|sar\s+and\s+optical)\b", re.IGNORECASE),
    re.compile(r"\b(cross[- ]modal|joint\s+analysis)\b", re.IGNORECASE),
    re.compile(r"\b(fuse|fusion)\b", re.IGNORECASE),
    re.compile(r"\btogether\s+to\s+(identify|detect|analyze|classify)\b", re.IGNORECASE),
]

_CHANGE_VQA_PATTERNS = [
    re.compile(r"\bwhat\s+changed\b", re.IGNORECASE),
    re.compile(r"\b(change\s+occur|changed\s+between|change\s+between)\b", re.IGNORECASE),
    re.compile(
        r"\bbetween\s+(these\s+)?(two\s+)?(dates|scenes|images|acquisitions|periods|years|months)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(increased[,\s]+decreased|increase[,\s]+decrease|remained\s+unchanged)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(bi[- ]temporal|temporal\s+change|change\s+detection)\b", re.IGNORECASE),
    re.compile(r"\b(pre[- ]event|post[- ]event|pre\s+and\s+post)\b", re.IGNORECASE),
    re.compile(r"\b(difference|differences)\s+between\b", re.IGNORECASE),
]

_GROUNDING_PATTERNS = [
    re.compile(r"\b(highlight|pinpoint|segment|outline)\b", re.IGNORECASE),
    re.compile(r"\b(bounding\s*box|bbox|exact\s+location|coordinates\s+of)\b", re.IGNORECASE),
    re.compile(r"\blocat(e|ing|ion)\b", re.IGNORECASE),
    re.compile(r"\bwhere\s+(is|are)\b", re.IGNORECASE),
]


def classify_intent(query: str) -> IntentClassification:
    """Classify user query into a fixed TaskType.

    Single source of truth: outputs IntentClassification with task_type only.
    No probabilistic confidence scores, free-form text, or redundant boolean flags.
    """
    normalized = query.strip() if query else ""
    if not normalized:
        return IntentClassification(task_type=TaskType.VQA)

    # 1. Archive Search
    if _ARCHIVE_SEARCH_PATTERN.search(normalized):
        return IntentClassification(task_type=TaskType.ARCHIVE_SEARCH_BONUS)

    # 2. Cross-Modal Fusion
    for pattern in _FUSION_PATTERNS:
        if pattern.search(normalized):
            return IntentClassification(task_type=TaskType.FUSION)

    # 3. Change-VQA / Bi-temporal
    for pattern in _CHANGE_VQA_PATTERNS:
        if pattern.search(normalized):
            return IntentClassification(task_type=TaskType.CHANGE_VQA)

    # 4. Grounding / Localization
    for pattern in _GROUNDING_PATTERNS:
        if pattern.search(normalized):
            return IntentClassification(task_type=TaskType.GROUNDING)

    # 5. Default: Single-Image VQA
    return IntentClassification(task_type=TaskType.VQA)
