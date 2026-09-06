"""Pure deterministic verification rules (SHIVA-004, F15/F16)."""

from __future__ import annotations

import re

from app.contracts import Evidence, EvidenceType, ImageInput, Modality
from app.verification.schemas import (
    AbstentionReasonCode,
    DisagreementCategory,
    DisagreementRecord,
    VerificationPolicy,
)

_OPTICAL_SPECTRAL_KEYWORDS: tuple[str, ...] = (
    "ndvi",
    "ndwi",
    "true color",
    "natural color",
    "false color",
    "red band",
    "green band",
    "blue band",
    "spectral reflectance",
    "rgb color",
    "optical color",
    "visual color",
)

_NUMERIC_METRIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("water_fraction", re.compile(r"water[\s_]*fraction[\s:=]+([0-9]*\.?[0-9]+)", re.IGNORECASE)),
    ("cloud_fraction", re.compile(r"cloud[\s_]*fraction[\s:=]+([0-9]*\.?[0-9]+)", re.IGNORECASE)),
    (
        "area_km2",
        re.compile(
            r"(?:area|flooded area)[\s_]*(?:km2|sqkm)?[\s:=]+([0-9]*\.?[0-9]+)",
            re.IGNORECASE,
        ),
    ),
    ("count", re.compile(r"(?:count|detected)[\s:=]+([0-9]+)", re.IGNORECASE)),
]


def evaluate_empty_evidence(evidence: list[Evidence]) -> tuple[bool, str | None]:
    """RULE-VERIFY-01: Empty Evidence Gate.

    Forces explicit typed abstention if tools produced zero evidence items.
    """
    if not evidence:
        return (
            True,
            (
                f"{AbstentionReasonCode.NO_EVIDENCE_PRODUCED}: "
                "Tools produced no evidence to answer the query."
            ),
        )
    return False, None


def evaluate_confidence_floor(
    evidence: list[Evidence],
    min_floor: float,
) -> tuple[list[Evidence], list[str], bool, str | None]:
    """RULE-VERIFY-02: Confidence Floor Gate.

    Filters evidence below the policy floor. If all items fail, forces typed abstention.
    """
    surviving: list[Evidence] = []
    filtered_ids: list[str] = []

    for item in evidence:
        if item.confidence >= min_floor:
            surviving.append(item)
        else:
            filtered_ids.append(item.id)

    if not surviving:
        return (
            [],
            filtered_ids,
            True,
            (
                f"{AbstentionReasonCode.INSUFFICIENT_CONFIDENCE}: Evidence confidence falls "
                f"below the reliability threshold ({min_floor:.2f})."
            ),
        )

    return surviving, filtered_ids, False, None


def evaluate_sensor_compatibility(
    raw_query: str | None,
    images: list[ImageInput] | None,
) -> tuple[bool, str | None]:
    """RULE-VERIFY-03: Sensor Physical Incompatibility Gate.

    Intercepts physical impossibilities (e.g. spectral properties queried on SAR-only data).
    """
    if not raw_query or not images:
        return False, None

    all_sar = all(img.modality == Modality.SAR for img in images)
    if all_sar:
        normalized_query = raw_query.lower()
        if any(kw in normalized_query for kw in _OPTICAL_SPECTRAL_KEYWORDS):
            return (
                True,
                (
                    f"{AbstentionReasonCode.SENSOR_PHYSICAL_LIMITATION}: SAR sensors record "
                    "microwave backscatter (roughness/dielectric properties), not optical "
                    "spectral reflectance or visual color."
                ),
            )

    return False, None


def evaluate_cloud_sar_reconciliation(
    evidence: list[Evidence],
) -> list[DisagreementRecord]:
    """RULE-VERIFY-04: Optical Cloud vs. SAR Radar Reconciliation.

    When optical is cloud-affected and SAR provides flood/water evidence, preserve SAR
    evidence and surface optical cloud limitation transparently. DO NOT abstain.
    """
    records: list[DisagreementRecord] = []

    has_cloud_limitation = False
    cloud_evidence_ids: list[str] = []
    has_sar_water = False

    for e in evidence:
        payload = e.payload
        if payload.get("optical_inconclusive") is True or payload.get("cloud_fraction", 0.0) > 0.0:
            has_cloud_limitation = True
            cloud_evidence_ids.append(e.id)
        if "water_mask" in payload or "water_fraction" in payload:
            has_sar_water = True

    if has_cloud_limitation and has_sar_water:
        records.append(
            DisagreementRecord(
                rule_id="RULE-VERIFY-04",
                category=DisagreementCategory.COMPLEMENTARY_OBSERVATION,
                description=(
                    "Optical observation is limited by cloud cover; SAR microwave backscatter "
                    "independently confirms surface water."
                ),
                action_taken="reconciled",
                conflicting_evidence_ids=cloud_evidence_ids,
            )
        )

    return records


def evaluate_structured_numeric_grounding(
    evidence: list[Evidence],
    policy: VerificationPolicy,
) -> tuple[list[DisagreementRecord], float]:
    """RULE-VERIFY-06: Structured Numeric Claim Grounding.

    Deterministically cross-references explicit numeric metric claims in TEXT payloads
    against STATS payload key-values. Downgrades confidence when unsupported.
    """
    records: list[DisagreementRecord] = []
    penalty = 0.0

    # Collect known ground-truth metrics from STATS evidence payloads
    stats_scalars: dict[str, float] = {}
    for e in evidence:
        if e.type == EvidenceType.STATS and isinstance(e.payload, dict):
            for k, v in e.payload.items():
                if isinstance(v, (int, float)):
                    stats_scalars[k.lower()] = float(v)

    # Inspect TEXT evidence for asserted structured metrics
    for e in evidence:
        if e.type == EvidenceType.TEXT and isinstance(e.payload, dict):
            text = e.payload.get("text") or e.payload.get("note") or ""
            if not isinstance(text, str):
                continue

            for metric_key, pattern in _NUMERIC_METRIC_PATTERNS:
                match = pattern.search(text)
                if match:
                    claimed_val = float(match.group(1))
                    if metric_key in stats_scalars:
                        actual_val = stats_scalars[metric_key]
                        if abs(claimed_val - actual_val) > 0.01:
                            records.append(
                                DisagreementRecord(
                                    rule_id="RULE-VERIFY-06",
                                    category=DisagreementCategory.UNSUPPORTED_NUMERIC_CLAIM,
                                    description=(
                                        f"Text claims {metric_key} {claimed_val}, "
                                        f"but STATS payload has {actual_val}."
                                    ),
                                    action_taken="downgraded",
                                    conflicting_evidence_ids=[e.id],
                                )
                            )
                            penalty += policy.unsupported_numeric_penalty
                    else:
                        # Metric claimed in text but no corresponding STATS payload exists
                        records.append(
                            DisagreementRecord(
                                rule_id="RULE-VERIFY-06",
                                category=DisagreementCategory.UNSUPPORTED_NUMERIC_CLAIM,
                                description=(
                                    f"Text asserts quantitative {metric_key} {claimed_val} without "
                                    "supporting STATS evidence."
                                ),
                                action_taken="downgraded",
                                conflicting_evidence_ids=[e.id],
                            )
                        )
                        penalty += policy.unsupported_numeric_penalty

    return records, min(penalty, policy.max_total_penalty)


def evaluate_cross_modal_conflict(
    evidence: list[Evidence],
    images: list[ImageInput] | None,
    policy: VerificationPolicy,
) -> tuple[bool, str | None, list[DisagreementRecord], float]:
    """RULE-VERIFY-CONFLICT: Irreconcilable Cross-Modal Contradiction.

    Implementation-level rule addition directly grounded in:
    - DESIGN.md §5 (Sensor Disagreements: cross-sensor conflict resolution),
    - DESIGN.md §7.2 (Verification Failure Modes: cross-modal contradiction handling), and
    - DESIGN.md §9 (Verification Output Contract: SEVERE_MODALITY_CONFLICT abstention code).

    Evaluates whether optical and SAR assert direct, irreconcilable contradictions on the
    identical target/region under clear observing conditions (where optical is not obscured
    by cloud cover). When contradictory claims occur at high confidence across modalities,
    this rule forces explicit typed abstention (AbstentionReasonCode.SEVERE_MODALITY_CONFLICT)
    rather than arbitrarily preferring one modality or averaging contradictory confidences.
    """
    records: list[DisagreementRecord] = []

    # Build modality attribution per evidence item
    image_modality_map: dict[str, Modality] = {}
    if images:
        for img in images:
            image_modality_map[img.id] = img.modality

    optical_items: list[Evidence] = []
    sar_items: list[Evidence] = []

    for e in evidence:
        modality: Modality | None = None
        if "modality" in e.payload:
            val = str(e.payload["modality"]).lower()
            if val == "optical":
                modality = Modality.OPTICAL
            elif val == "sar":
                modality = Modality.SAR
        elif "image_id" in e.payload and str(e.payload["image_id"]) in image_modality_map:
            modality = image_modality_map[str(e.payload["image_id"])]

        if modality is Modality.OPTICAL:
            optical_items.append(e)
        elif modality is Modality.SAR:
            sar_items.append(e)

    # Compare optical vs SAR evidence on matching region
    for opt in optical_items:
        for sar in sar_items:
            opt_region = opt.payload.get("region", "full_scene")
            sar_region = sar.payload.get("region", "full_scene")
            if opt_region != sar_region:
                continue  # Different regions -> not comparable for direct conflict

            # Check if optical is cloud-free and asserts dry land
            opt_cloud = float(opt.payload.get("cloud_fraction", 0.0))
            opt_inconclusive = bool(opt.payload.get("optical_inconclusive", False))
            opt_water = float(opt.payload.get("water_fraction", 0.0))

            # Check if SAR asserts water
            sar_water = float(sar.payload.get("water_fraction", 0.0))

            # Direct contradiction: optical is clear (0% cloud) asserting 0% water,
            # while SAR asserts >=80% water
            if not opt_inconclusive and opt_cloud == 0.0 and opt_water < 0.05 and sar_water >= 0.80:
                record = DisagreementRecord(
                    rule_id="RULE-VERIFY-CONFLICT",
                    category=DisagreementCategory.CROSS_MODAL_CONFLICT,
                    description=(
                        f"Direct contradiction on region '{opt_region}': Optical asserts dry land "
                        f"(water_fraction={opt_water:.2f}) under clear skies, while SAR asserts "
                        f"standing water (water_fraction={sar_water:.2f})."
                    ),
                    action_taken="abstained",
                    conflicting_evidence_ids=[opt.id, sar.id],
                )
                records.append(record)
                return (
                    True,
                    (
                        f"{AbstentionReasonCode.SEVERE_MODALITY_CONFLICT}: "
                        "Irreconcilable contradiction between Optical and SAR observations on "
                        f"region '{opt_region}' without cloud obstruction."
                    ),
                    records,
                    policy.severe_conflict_penalty,
                )

    return False, None, records, 0.0
