"""Tests for evidence retrieval: candidate gathering over the graph store."""

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from verdict.adapters.inmemory_store import InMemoryGraphVectorStore
from verdict.models import Edge, EvidenceItem, Stance
from verdict.retrieval import gather_candidates, score_stances

from tests.factories import make_paper


def _user_text(messages: list[ModelMessage]) -> str:
    """Return the text of the latest user prompt in a message history."""
    for message in reversed(messages):
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                return part.content
    return ""


def _stance_for(title_to_stance: dict[str, Stance]) -> FunctionModel:
    """Build a model that returns a stance keyed on the paper title in the prompt."""

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = _user_text(messages)
        stance = next((s for title, s in title_to_stance.items() if title in prompt), Stance.NEUTRAL)
        args = {"stance": stance.value, "snippet": "snip", "rationale": "why"}
        return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=args)])

    return FunctionModel(respond)


async def test_gather_candidates_unions_recall_foundations_and_neighbours():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("recall", cited_by=0), [1.0, 0.0])
    await store.upsert_paper(make_paper("neighbour", cited_by=0), [0.0, 1.0])
    await store.upsert_paper(make_paper("foundation", cited_by=100), [0.9, 0.1])
    await store.upsert_edge(Edge(src="recall", dst="neighbour", kind="cites"))

    candidates = await gather_candidates([1.0, 0.0], store=store, k=1, min_cited=50)

    ids = {p.openalex_id for p in candidates}
    assert {"recall", "neighbour", "foundation"} <= ids


async def test_gather_candidates_dedups_papers_seen_in_multiple_sources():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("both", cited_by=100), [1.0, 0.0])

    candidates = await gather_candidates([1.0, 0.0], store=store, k=5, min_cited=50)

    assert [p.openalex_id for p in candidates] == ["both"]


async def test_gather_candidates_drops_retracted_papers():
    store = InMemoryGraphVectorStore()
    await store.upsert_paper(make_paper("ok", cited_by=0), [1.0, 0.0])
    await store.upsert_paper(make_paper("bad", cited_by=0, is_retracted=True), [0.99, 0.01])

    candidates = await gather_candidates([1.0, 0.0], store=store, k=5, min_cited=50)

    ids = {p.openalex_id for p in candidates}
    assert "ok" in ids
    assert "bad" not in ids


async def test_score_stances_returns_one_evidence_item_per_paper():
    papers = [make_paper("P1"), make_paper("P2")]
    model = _stance_for({"P1": Stance.SUPPORTS, "P2": Stance.SUPPORTS})

    items = await score_stances("a claim", papers, model=model)

    assert len(items) == 2
    assert all(isinstance(item, EvidenceItem) for item in items)
    assert [item.paper.openalex_id for item in items] == ["P1", "P2"]


async def test_score_stances_judges_each_paper_independently():
    papers = [make_paper("PRO"), make_paper("CON"), make_paper("OFF")]
    model = _stance_for({"PRO": Stance.SUPPORTS, "CON": Stance.CONTRADICTS, "OFF": Stance.OFF_TOPIC})

    items = await score_stances("a claim", papers, model=model)

    by_id = {item.paper.openalex_id: item.stance for item in items}
    assert by_id == {"PRO": Stance.SUPPORTS, "CON": Stance.CONTRADICTS, "OFF": Stance.OFF_TOPIC}


async def test_score_stances_carries_the_llm_snippet_and_rationale():
    model = _stance_for({"P1": Stance.SUPPORTS})

    (item,) = await score_stances("a claim", [make_paper("P1")], model=model)

    assert item.snippet == "snip"
    assert item.rationale == "why"


async def test_score_stances_of_no_papers_is_empty():
    model = _stance_for({})

    assert await score_stances("a claim", [], model=model) == []
