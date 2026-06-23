"""Claim triage: decide whether a claim is empirically checkable before any spend."""

from pydantic_ai import Agent
from pydantic_ai.models import Model

from verdict.models import TriageResult
from verdict.prompting import render_prompt


async def triage_claim(claim: str, *, model: Model) -> TriageResult:
    """Decide whether a claim is empirically checkable, with an optional refinement.

    Parameters
    ----------
    claim : str
        The claim to triage.
    model : Model
        The model that judges checkability.

    Returns
    -------
    TriageResult
        Whether the claim is checkable, a sharper rewrite or None, and the reason.
    """
    agent = Agent(model=model, output_type=TriageResult, system_prompt=render_prompt("triage_system.j2"))
    return (await agent.run(render_prompt("triage_user.j2", claim=claim))).output
