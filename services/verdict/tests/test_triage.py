"""Tests for the claim triage gate."""

from verdict.models import TriageResult
from verdict.triage import triage_claim

from tests.model_stubs import triage_model


async def test_triage_claim_returns_a_triage_result():
    result = await triage_claim("Creatine improves short-term memory.", model=triage_model(checkable=True))

    assert isinstance(result, TriageResult)
    assert result.checkable is True


async def test_triage_claim_flags_a_non_checkable_claim_with_a_refinement():
    model = triage_model(checkable=False, refined="A sharper, checkable rewrite.")

    result = await triage_claim("Modern art is bad.", model=model)

    assert result.checkable is False
    assert result.refined_claim == "A sharper, checkable rewrite."


async def test_triage_claim_passes_the_claim_into_the_prompt():
    model = triage_model(checkable=True, marker="MARKER_CLAIM")

    result = await triage_claim("MARKER_CLAIM", model=model)

    assert result.checkable is True
