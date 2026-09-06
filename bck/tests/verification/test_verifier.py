"""Conservative claim-verification tests."""

from app.verification import VerificationStatus, verify_answer


def test_verifier_removes_claim_not_supported_by_observations() -> None:
    """An unsupported pollution claim must not survive evidence-based verification."""
    result = verify_answer(
        candidate_answer=(
            "A river is visible and industrial pollution is contaminating the water."
        ),
        supporting_observations=["A river is visible in the scene."],
    )

    assert result.status is VerificationStatus.PARTIALLY_SUPPORTED
    assert result.verified_text == "A river is visible."
    assert result.rejected_claims == ("industrial pollution is contaminating the water",)
    assert "pollution" not in result.verified_text.lower()
