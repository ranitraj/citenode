"""Load SciFact gold claims and map their labels to citenode verdicts."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from verdict.models import Verdict

# SciFact evidence labels and the no-evidence case, mapped to citenode verdicts (ADR 0013).
_LABEL_TO_VERDICT = {
    "SUPPORT": Verdict.SUPPORTED,
    "CONTRADICT": Verdict.REFUTED,
    "NOINFO": Verdict.INSUFFICIENT,
}


class GoldAbstract(BaseModel):
    """One SciFact corpus abstract supplied as gold evidence."""

    doc_id: str
    title: str
    abstract: str


class GoldClaim(BaseModel):
    """A SciFact claim with its gold verdict and the abstracts it cites."""

    claim_id: str
    claim: str
    gold_verdict: Verdict
    abstracts: list[GoldAbstract]


def scifact_label_to_verdict(label: str) -> Verdict:
    """Map a SciFact label to the citenode verdict it corresponds to.

    Parameters
    ----------
    label : str
        A SciFact label: ``SUPPORT``, ``CONTRADICT``, or ``NOINFO``.

    Returns
    -------
    Verdict
        The corresponding verdict.

    Raises
    ------
    KeyError
        If the label is not a known SciFact label.
    """
    return _LABEL_TO_VERDICT[label]


def load_gold(claims_path: Path, corpus_path: Path) -> list[GoldClaim]:
    """Load SciFact claims and resolve each one's cited abstracts into a gold claim.

    Parameters
    ----------
    claims_path : Path
        The SciFact claims JSONL file (``id``, ``claim``, ``evidence``, ``cited_doc_ids``).
    corpus_path : Path
        The SciFact corpus JSONL file (``doc_id``, ``title``, ``abstract`` sentences).

    Returns
    -------
    list[GoldClaim]
        One gold claim per claims record, with its cited abstracts resolved and its
        label mapped to a verdict.
    """
    corpus = _load_corpus(corpus_path)
    gold: list[GoldClaim] = []
    for record in _read_jsonl(claims_path):
        cited = [str(doc_id) for doc_id in record.get("cited_doc_ids", [])]
        gold.append(
            GoldClaim(
                claim_id=str(record["id"]),
                claim=record["claim"],
                gold_verdict=scifact_label_to_verdict(_claim_label(record.get("evidence", {}))),
                abstracts=[corpus[doc_id] for doc_id in cited if doc_id in corpus],
            )
        )
    return gold


def _load_corpus(corpus_path: Path) -> dict[str, GoldAbstract]:
    """Index the SciFact corpus abstracts by document id.

    Parameters
    ----------
    corpus_path : Path
        The SciFact corpus JSONL file.

    Returns
    -------
    dict[str, GoldAbstract]
        Each corpus abstract keyed by its document id, with sentences joined.
    """
    corpus: dict[str, GoldAbstract] = {}
    for record in _read_jsonl(corpus_path):
        doc_id = str(record["doc_id"])
        corpus[doc_id] = GoldAbstract(
            doc_id=doc_id, title=record.get("title", ""), abstract=" ".join(record.get("abstract", []))
        )
    return corpus


def _claim_label(evidence: dict[str, Any]) -> str:
    """Derive a claim-level SciFact label from its per-document evidence.

    Parameters
    ----------
    evidence : dict[str, Any]
        The claim's evidence, mapping a document id to its labeled rationale entries.

    Returns
    -------
    str
        The first evidence entry's label, or ``NOINFO`` when there is no evidence.
    """
    for entries in evidence.values():
        for entry in entries:
            return str(entry["label"])
    return "NOINFO"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of records.

    Parameters
    ----------
    path : Path
        The JSONL file to read.

    Returns
    -------
    list[dict[str, Any]]
        One parsed record per non-blank line.
    """
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
