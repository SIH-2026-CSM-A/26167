"""Pure deterministic verification rules (SHIVA-004, F15/F16)."""

from __future__ import annotations

import re

from app.contracts import DegradationNotice, Evidence, EvidenceType, ImageInput, Modality
from app.verification.schemas import (
    AbstentionReasonCode,
    CrossModalRelationship,
    DisagreementCategory,
    DisagreementRecord,
    VerificationPolicy,
)

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


def evaluate_narrative_claim_grounding(
    evidence: list[Evidence],
    supporting_observations: list[str],
) -> tuple[list[Evidence], list[DisagreementRecord]]:
    """RULE-VERIFY-09: Narrative Claim Grounding.

    Splits narrative TEXT evidence into atomic claims (sentence and conjunction
    boundaries), keeps only claims backed by a supporting observation, downgrades
    evidence content to the supported subset, records a DisagreementRecord per
    stripped claim. Confidence is set to the supported fraction of total claims,
    so a fully-stripped claim still falls through to the confidence floor gate.
    """
    observations = tuple(item.strip() for item in supporting_observations if item.strip())
    records: list[DisagreementRecord] = []
    updated: list[Evidence] = []

    for item in evidence:
        text = item.payload.get("verified_answer") or item.payload.get("raw_model_answer")
        if item.type != EvidenceType.TEXT or not isinstance(text, str) or not text.strip():
            updated.append(item)
            continue

        claims = _split_claims(text)
        if not claims:
            updated.append(item)
            continue

        supported = tuple(claim for claim in claims if _claim_is_supported(claim, observations))
        rejected = tuple(claim for claim in claims if claim not in supported)

        for claim in rejected:
            records.append(
                DisagreementRecord(
                    rule_id="RULE-VERIFY-09",
                    category=DisagreementCategory.UNSUPPORTED_NARRATIVE_CLAIM,
                    description=(
                        f"Narrative claim '{claim}' is not supported by any grounded observation."
                    ),
                    action_taken="downgraded",
                    conflicting_evidence_ids=[item.id],
                )
            )

        new_payload = dict(item.payload)
        new_payload["verified_answer"] = " ".join(_as_sentence(claim) for claim in supported)
        new_payload["rejected_claims"] = [*item.payload.get("rejected_claims", []), *rejected]
        updated.append(
            item.model_copy(
                update={"payload": new_payload, "confidence": len(supported) / len(claims)}
            )
        )

    return updated, records


def evaluate_spatial_geometry_consistency(
    evidence: list[Evidence],
    policy: VerificationPolicy,
) -> tuple[list[DisagreementRecord], float]:
    """RULE-VERIFY-07: Conditional Spatial Geometry Consistency.

    Evaluates spatial geometry consistency between terrestrial detections (BBOX) and
    water/flood extent masks (MASK). Under the current standardized contract, no shared
    coordinate reference system (CRS) or standardized geometry schema is available across
    specialist tools (DESIGN.md §6 Table 6, §15.2).

    When both BBOX and MASK evidence exist, this evaluator safely records NOT_COMPARABLE
    with action_taken="caveated" and penalty 0.0, as mandated by DESIGN.md Table 6:
    "If geometries are missing or incompatible, record NOT_COMPARABLE."
    """
    bbox_items = [e for e in evidence if e.type == EvidenceType.BBOX]
    mask_items = [e for e in evidence if e.type == EvidenceType.MASK]

    if not bbox_items or not mask_items:
        return [], 0.0

    participating_ids: list[str] = []
    seen: set[str] = set()
    for e in evidence:
        if (e.type == EvidenceType.BBOX or e.type == EvidenceType.MASK) and e.id not in seen:
            seen.add(e.id)
            participating_ids.append(e.id)

    record = DisagreementRecord(
        rule_id="RULE-VERIFY-07",
        category=DisagreementCategory.NOT_COMPARABLE,
        description=(
            "Spatial bounding box and mask geometries cannot be evaluated for physical "
            "consistency because a standardized compatible geometry representation or "
            "shared verified coordinate reference frame is not available."
        ),
        action_taken="caveated",
        conflicting_evidence_ids=participating_ids,
    )
    return [record], 0.0


def evaluate_spatial_extent_comparison(
    evidence: list[Evidence],
    policy: VerificationPolicy,
) -> tuple[list[DisagreementRecord], float]:
    """RULE-VERIFY-08: Cross-Modal Spatial Extent Comparison.

    Evaluates spatial extent overlap between multiple segmentation masks (MASK).
    Under the current standardized contract, no shared coordinate reference system
    (CRS), georeferenced raster alignment, or standardized mask schema is available
    across specialist tools (DESIGN.md §6 Table 6, §15.2).

    When at least two MASK evidence items exist, this evaluator safely records
    NOT_COMPARABLE with action_taken="caveated" and penalty 0.0, as mandated by
    DESIGN.md Table 6: "If incompatible or absent, record NOT_COMPARABLE."
    """
    mask_items = [e for e in evidence if e.type == EvidenceType.MASK]
    if len(mask_items) < 2:
        return [], 0.0

    participating_ids: list[str] = []
    seen: set[str] = set()
    for e in evidence:
        if e.type == EvidenceType.MASK and e.id not in seen:
            seen.add(e.id)
            participating_ids.append(e.id)

    record = DisagreementRecord(
        rule_id="RULE-VERIFY-08",
        category=DisagreementCategory.NOT_COMPARABLE,
        description=(
            "Spatial segmentation masks cannot be evaluated for spatial extent consistency "
            "because a standardized compatible geometry representation or shared verified "
            "coordinate reference frame is not available."
        ),
        action_taken="caveated",
        conflicting_evidence_ids=participating_ids,
    )
    return [record], 0.0


def evaluate_scattering_divergence(
    evidence: list[Evidence],
    policy: VerificationPolicy | None = None,
) -> tuple[list[DisagreementRecord], float]:
    """RULE-VERIFY-05: Scattering Mechanism Divergence.

    Evaluates whether multi-sensor Optical and SAR observations indicate divergent
    physical scattering mechanisms over vegetation or built structures (DESIGN.md Table 6, §7).

    - If Optical and SAR report explicitly divergent scattering mechanisms, records
      COMPLEMENTARY_OBSERVATION with action_taken="caveated" and penalty 0.0 without abstaining.
    - If scattering mechanisms match, no divergence is recorded.
    - If Optical and SAR evidence exist but scattering semantics cannot be safely compared
      under the current contract (e.g. uncharacterized payloads), safely records NOT_COMPARABLE
      with action_taken="caveated" and penalty 0.0.
    - If evidence is not multimodal (lacks optical or SAR items), returns ([], 0.0).
    """
    optical_items = [
        e
        for e in evidence
        if isinstance(e.payload, dict)
        and (e.payload.get("modality") == "optical" or "optical" in e.tool.lower())
    ]
    sar_items = [
        e
        for e in evidence
        if isinstance(e.payload, dict)
        and (
            e.payload.get("modality") == "sar"
            or "sar" in e.tool.lower()
            or "water_mask" in e.payload
        )
    ]

    if not optical_items or not sar_items:
        return [], 0.0

    participating_ids: list[str] = []
    seen: set[str] = set()
    for e in evidence:
        if (e in optical_items or e in sar_items) and e.id not in seen:
            seen.add(e.id)
            participating_ids.append(e.id)

    opt_mechanisms: set[str] = set()
    for e in optical_items:
        val = e.payload.get("scattering_mechanism") or e.payload.get("surface_characteristic")
        if isinstance(val, str) and val.strip():
            opt_mechanisms.add(val.strip().lower())

    sar_mechanisms: set[str] = set()
    for e in sar_items:
        val = e.payload.get("scattering_mechanism") or e.payload.get("surface_characteristic")
        if isinstance(val, str) and val.strip():
            sar_mechanisms.add(val.strip().lower())

    # Fallback: if scattering semantics cannot be safely compared under current contract
    if not opt_mechanisms or not sar_mechanisms:
        record = DisagreementRecord(
            rule_id="RULE-VERIFY-05",
            category=DisagreementCategory.NOT_COMPARABLE,
            description=(
                "Optical and SAR surface scattering mechanisms cannot be evaluated for physical "
                "divergence because structured scattering mechanism attributes are not available "
                "in the evidence payloads."
            ),
            action_taken="caveated",
            conflicting_evidence_ids=participating_ids,
        )
        return [record], 0.0

    # Matching mechanisms -> no divergence
    if opt_mechanisms == sar_mechanisms:
        return [], 0.0

    # Divergent scattering mechanisms
    record = DisagreementRecord(
        rule_id="RULE-VERIFY-05",
        category=DisagreementCategory.COMPLEMENTARY_OBSERVATION,
        description=(
            f"Optical surface reflection ({', '.join(sorted(opt_mechanisms))}) and "
            f"SAR backscatter ({', '.join(sorted(sar_mechanisms))}) indicate divergent "
            "physical scattering mechanisms over the observed terrain."
        ),
        action_taken="caveated",
        conflicting_evidence_ids=participating_ids,
    )
    return [record], 0.0


def classify_cross_modal_relationship(
    ev1: Evidence,
    ev2: Evidence,
    policy: VerificationPolicy | None = None,
) -> CrossModalRelationship:
    """Classify the relationship between two multi-sensor evidence items (DESIGN.md §7).

    Evaluates evidence against five mutually exclusive relationship states in deterministic order:
    1. INSUFFICIENT_EVIDENCE: either evidence item fails the minimum confidence floor.
    2. NOT_COMPARABLE: evidence representations or footprints cannot safely be juxtaposed
       under current contracts (e.g. text caption vs spatial geometry, bounding box vs mask,
       or disjoint spatial regions).
    3. COMPLEMENTARY: differing observations explained by sensor physics (e.g. optical cloud
       cover limitation alongside SAR flood observation per RULE-VERIFY-04).
    4. DISAGREEMENT: modalities evaluate the same comparable footprint under clear conditions
       and assert directly contradictory findings (per RULE-VERIFY-CONFLICT).
    5. AGREEMENT: modalities evaluate the same comparable footprint and produce consistent findings.
    """
    active_policy = policy or VerificationPolicy()

    # Priority 1: Confidence floor check
    if (
        ev1.confidence < active_policy.min_confidence_floor
        or ev2.confidence < active_policy.min_confidence_floor
    ):
        return CrossModalRelationship.INSUFFICIENT_EVIDENCE

    # Priority 2: Incompatible representations or spatial footprints
    # 2a. Disjoint regions
    r1 = ev1.payload.get("region")
    r2 = ev2.payload.get("region")
    if r1 is not None and r2 is not None and r1 != r2:
        return CrossModalRelationship.NOT_COMPARABLE

    # 2b. Caption (TEXT) paired with unreferenced spatial geometries (BBOX or MASK)
    if (ev1.type == EvidenceType.TEXT and ev2.type in (EvidenceType.BBOX, EvidenceType.MASK)) or (
        ev2.type == EvidenceType.TEXT and ev1.type in (EvidenceType.BBOX, EvidenceType.MASK)
    ):
        return CrossModalRelationship.NOT_COMPARABLE

    # 2c. BBOX paired with MASK (incompatible spatial geometry representations per RULE-VERIFY-07)
    if (ev1.type == EvidenceType.BBOX and ev2.type == EvidenceType.MASK) or (
        ev1.type == EvidenceType.MASK and ev2.type == EvidenceType.BBOX
    ):
        return CrossModalRelationship.NOT_COMPARABLE

    # Priority 3: Sensor physics complementarity (Optical clouds + SAR radar water
    # per RULE-VERIFY-04)
    opt_cloud_1 = (
        ev1.payload.get("optical_inconclusive") is True
        or float(ev1.payload.get("cloud_fraction", 0.0)) > 0.0
    )
    opt_cloud_2 = (
        ev2.payload.get("optical_inconclusive") is True
        or float(ev2.payload.get("cloud_fraction", 0.0)) > 0.0
    )

    sar_water_1 = (
        ev1.payload.get("modality") == "sar"
        or "sar" in ev1.tool.lower()
        or "water_mask" in ev1.payload
        or float(ev1.payload.get("water_fraction", 0.0)) > 0.0
    )
    sar_water_2 = (
        ev2.payload.get("modality") == "sar"
        or "sar" in ev2.tool.lower()
        or "water_mask" in ev2.payload
        or float(ev2.payload.get("water_fraction", 0.0)) > 0.0
    )

    if (opt_cloud_1 and sar_water_2) or (opt_cloud_2 and sar_water_1):
        return CrossModalRelationship.COMPLEMENTARY

    # Priority 4: Direct cross-modal conflict / contradiction (per RULE-VERIFY-CONFLICT)
    wf1 = ev1.payload.get("water_fraction")
    wf2 = ev2.payload.get("water_fraction")
    if isinstance(wf1, (int, float)) and isinstance(wf2, (int, float)):
        c1 = float(ev1.payload.get("cloud_fraction", 0.0))
        c2 = float(ev2.payload.get("cloud_fraction", 0.0))
        # Clear sky contradiction: one asserts dry land and other asserts standing water
        if c1 == 0.0 and c2 == 0.0:
            if (wf1 < 0.10 and wf2 >= 0.70) or (wf2 < 0.10 and wf1 >= 0.70):
                return CrossModalRelationship.DISAGREEMENT

    # Priority 5: Consistent / agreement findings
    return CrossModalRelationship.AGREEMENT


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


def evaluate_optical_degradation(
    images: list[ImageInput] | None,
    threshold: float = 0.20,
) -> DegradationNotice | None:
    """Evaluate optical input images for cloud degradation and emit DegradationNotice if exceeded.

    Inspects each optical ImageInput's metadata for `cloud_fraction`. If any optical input's
    cloud fraction meets or exceeds the configured degradation threshold (default 0.20,
    calibrated against the clean 1.87% Bolivia_103757_S2Hand.tif baseline), constructs a
    structured DegradationNotice recommending SAR fallback per SHIVA-006 / F22.
    """
    if not images:
        return None

    degraded_inputs: list[tuple[str, float]] = []
    for img in images:
        if img.modality == Modality.OPTICAL:
            cf = img.metadata.get("cloud_fraction")
            if cf is not None and float(cf) >= threshold:
                degraded_inputs.append((img.id, float(cf)))

    if not degraded_inputs:
        return None

    max_fraction = max(fraction for _, fraction in degraded_inputs)
    affected_ids = [img_id for img_id, _ in degraded_inputs]

    return DegradationNotice(
        degraded=True,
        metric_name="cloud_cover_fraction",
        metric_value=round(max_fraction, 4),
        threshold=round(threshold, 4),
        severity="warning",
        message=(
            f"Optical input '{affected_ids[0]}' exhibits {max_fraction * 100:.1f}% "
            f"cloud cover, exceeding the quality threshold of {threshold * 100:.1f}%."
        ),
        suggested_action=(
            "SAR-only fallback workflow recommended due to heavy cloud cover "
            "obscuring optical imagery."
        ),
        fallback_modality=Modality.SAR,
        affected_image_ids=affected_ids,
    )
