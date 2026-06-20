"""OpenAlex-backed literature source: seed search, work fetch, citation expansion."""

import asyncio
from typing import Any

from pyalex import Works
from pyalex.api import invert_abstract

from verdict.models import Work, WorkRef


class OpenAlexSource:
    """LiteratureSource adapter over the OpenAlex API via pyalex.

    The pyalex client is synchronous; each call is offloaded to a worker
    thread so the event loop stays responsive.
    """

    async def search_seeds(self, query: str, limit: int) -> list[WorkRef]:
        """Return seed works matching a claim query.

        Parameters
        ----------
        query : str
            The claim or search query.
        limit : int
            The maximum number of seed works to return.

        Returns
        -------
        list[WorkRef]
            References to the matching seed works, most relevant first.
        """
        page = await asyncio.to_thread(lambda: Works().search(query).get(per_page=limit))
        return [_to_work_ref(work) for work in page]

    async def fetch_work(self, work_id: str) -> Work:
        """Fetch a single work with its reconstructed abstract and metadata.

        Parameters
        ----------
        work_id : str
            The OpenAlex identifier, bare (``W123``) or as a full URL.

        Returns
        -------
        Work
            The fetched work with abstract, retraction flag, venue, topics, and refs.
        """
        raw = await asyncio.to_thread(lambda: Works()[_short_id(work_id)])
        return _to_work(raw)

    async def outgoing_refs(self, work_id: str) -> list[WorkRef]:
        """Return the works a given work cites (its referenced foundations).

        Parameters
        ----------
        work_id : str
            The citing work's identifier.

        Returns
        -------
        list[WorkRef]
            References to the cited works.
        """
        raw = await asyncio.to_thread(lambda: Works()[_short_id(work_id)])
        return [WorkRef(openalex_id=_short_id(ref), doi=None) for ref in raw.get("referenced_works", [])]

    async def incoming_citations(self, work_id: str, limit: int) -> list[WorkRef]:
        """Return works that cite a given work, surfacing potential refutations.

        Parameters
        ----------
        work_id : str
            The cited work's identifier.
        limit : int
            The maximum number of citing works to return.

        Returns
        -------
        list[WorkRef]
            References to the citing works.
        """
        page = await asyncio.to_thread(lambda: Works().filter(cites=_short_id(work_id)).get(per_page=limit))
        return [_to_work_ref(work) for work in page]


def _to_work(raw: dict[str, Any]) -> Work:
    """Map a raw OpenAlex work into a domain Work.

    Parameters
    ----------
    raw : dict[str, Any]
        A work object as returned by the OpenAlex API.

    Returns
    -------
    Work
        The mapped work; a missing abstract becomes the empty string.
    """
    return Work(
        openalex_id=_short_id(raw["id"]),
        doi=raw.get("doi"),
        title=raw["display_name"],
        year=raw["publication_year"],
        abstract=invert_abstract(raw.get("abstract_inverted_index")) or "",
        cited_by=raw["cited_by_count"],
        is_retracted=raw["is_retracted"],
        venue=_extract_venue(raw),
        topics=[topic["display_name"] for topic in raw.get("topics", [])],
        referenced_works=[_short_id(ref) for ref in raw.get("referenced_works", [])],
    )


def _to_work_ref(raw: dict[str, Any]) -> WorkRef:
    """Map a raw OpenAlex work into a lightweight WorkRef.

    Parameters
    ----------
    raw : dict[str, Any]
        A work object as returned by the OpenAlex API.

    Returns
    -------
    WorkRef
        The work's short id and DOI.
    """
    return WorkRef(openalex_id=_short_id(raw["id"]), doi=raw.get("doi"))


def _extract_venue(raw: dict[str, Any]) -> str | None:
    """Pull the publication venue name from a work's primary location.

    Parameters
    ----------
    raw : dict[str, Any]
        A work object as returned by the OpenAlex API.

    Returns
    -------
    str | None
        The source display name, or None when no venue is recorded.
    """
    location = raw.get("primary_location") or {}
    source = location.get("source") or {}
    return source.get("display_name")


def _short_id(openalex_id: str) -> str:
    """Reduce an OpenAlex id URL to its bare identifier.

    Parameters
    ----------
    openalex_id : str
        An id either bare (``W123``) or as a full URL.

    Returns
    -------
    str
        The trailing identifier segment.
    """
    return openalex_id.rsplit("/", 1)[-1]
