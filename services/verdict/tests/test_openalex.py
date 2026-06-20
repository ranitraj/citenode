"""Tests for the OpenAlex literature source adapter."""

import pytest
from verdict import ingest
from verdict.ingest.openalex import OpenAlexSource

# Mocked OpenAlex Work JSON, shaped like the live API responses.
SEED_WORK = {
    "id": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.7717/peerj.4375",
    "display_name": "The state of open access",
    "publication_year": 2018,
    "abstract_inverted_index": {"Despite": [0], "growing": [1], "interest": [2]},
    "cited_by_count": 294,
    "is_retracted": False,
    "primary_location": {"source": {"display_name": "PeerJ"}},
    "topics": [{"display_name": "Open Access"}, {"display_name": "Scholarly Communication"}],
    "referenced_works": ["https://openalex.org/W111", "https://openalex.org/W222"],
}

OTHER_WORK = {
    "id": "https://openalex.org/W333",
    "doi": None,
    "display_name": "A citing study",
    "publication_year": 2021,
    "abstract_inverted_index": {"It": [0], "cites": [1]},
    "cited_by_count": 5,
    "is_retracted": False,
    "primary_location": None,
    "topics": [],
    "referenced_works": [],
}

RETRACTED_WORK = {
    "id": "https://openalex.org/W999",
    "doi": "https://doi.org/10.1234/bad",
    "display_name": "A withdrawn result",
    "publication_year": 2015,
    "abstract_inverted_index": None,
    "cited_by_count": 0,
    "is_retracted": True,
    "primary_location": {"source": None},
    "topics": [],
    "referenced_works": [],
}


class _FakeWorks:
    """Stand-in for pyalex ``Works()`` that returns canned JSON without HTTP."""

    def __init__(self, *, single=None, page=None):
        self._single = single
        self._page = page or []

    def search(self, _s):
        """Mirror ``Works().search`` — returns self for chaining."""
        return self

    def filter(self, **_kw):
        """Mirror ``Works().filter`` — returns self for chaining."""
        return self

    def get(self, per_page=None, **_kw):
        """Mirror ``Works().get`` — return the canned page, sliced to per_page."""
        return self._page[:per_page] if per_page is not None else self._page

    def __getitem__(self, _work_id):
        return self._single


def _patch_works(monkeypatch, **kwargs):
    monkeypatch.setattr(ingest.openalex, "Works", lambda: _FakeWorks(**kwargs))


async def test_search_seeds_returns_work_refs(monkeypatch):
    _patch_works(monkeypatch, page=[SEED_WORK, OTHER_WORK])
    refs = await OpenAlexSource().search_seeds("open access", limit=2)
    assert [r.openalex_id for r in refs] == ["W2741809807", "W333"]
    assert refs[0].doi == "https://doi.org/10.7717/peerj.4375"


async def test_search_seeds_respects_limit(monkeypatch):
    _patch_works(monkeypatch, page=[SEED_WORK, OTHER_WORK])
    refs = await OpenAlexSource().search_seeds("open access", limit=1)
    assert [r.openalex_id for r in refs] == ["W2741809807"]


async def test_fetch_work_reconstructs_abstract(monkeypatch):
    _patch_works(monkeypatch, single=SEED_WORK)
    work = await OpenAlexSource().fetch_work("W2741809807")
    assert work.openalex_id == "W2741809807"
    assert work.title == "The state of open access"
    assert work.year == 2018
    assert work.abstract == "Despite growing interest"
    assert work.cited_by == 294
    assert work.venue == "PeerJ"
    assert work.topics == ["Open Access", "Scholarly Communication"]
    assert work.referenced_works == ["W111", "W222"]


async def test_fetch_work_carries_retraction_and_handles_missing_abstract(monkeypatch):
    _patch_works(monkeypatch, single=RETRACTED_WORK)
    work = await OpenAlexSource().fetch_work("W999")
    assert work.is_retracted is True
    assert work.abstract == ""
    assert work.venue is None


async def test_outgoing_refs_lists_referenced_works(monkeypatch):
    _patch_works(monkeypatch, single=SEED_WORK)
    refs = await OpenAlexSource().outgoing_refs("W2741809807")
    assert [r.openalex_id for r in refs] == ["W111", "W222"]


async def test_incoming_citations_returns_citing_refs(monkeypatch):
    _patch_works(monkeypatch, page=[OTHER_WORK])
    refs = await OpenAlexSource().incoming_citations("W2741809807", limit=25)
    assert [r.openalex_id for r in refs] == ["W333"]


@pytest.mark.parametrize("work_id", ["W2741809807", "https://openalex.org/W2741809807"])
async def test_fetch_work_accepts_bare_or_url_id(monkeypatch, work_id):
    _patch_works(monkeypatch, single=SEED_WORK)
    work = await OpenAlexSource().fetch_work(work_id)
    assert work.openalex_id == "W2741809807"
