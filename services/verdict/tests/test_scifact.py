"""Tests for SciFact gold-claim loading and label mapping."""

import json
from pathlib import Path

import pytest
from verdict.eval.scifact import load_gold, scifact_label_to_verdict
from verdict.models import Verdict


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")


def test_scifact_label_to_verdict_maps_the_three_labels():
    assert scifact_label_to_verdict("SUPPORT") is Verdict.SUPPORTED
    assert scifact_label_to_verdict("CONTRADICT") is Verdict.REFUTED
    assert scifact_label_to_verdict("NOINFO") is Verdict.INSUFFICIENT


def test_scifact_label_to_verdict_rejects_an_unknown_label():
    with pytest.raises(KeyError):
        scifact_label_to_verdict("MAYBE")


def test_load_gold_resolves_cited_abstracts_and_labels(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    claims = tmp_path / "claims.jsonl"
    _write_jsonl(
        corpus,
        [
            {"doc_id": 1, "title": "Paper One", "abstract": ["A.", "B."]},
            {"doc_id": 2, "title": "Paper Two", "abstract": ["C."]},
        ],
    )
    _write_jsonl(
        claims,
        [
            {
                "id": 10,
                "claim": "Claim one.",
                "evidence": {"1": [{"sentences": [0], "label": "SUPPORT"}]},
                "cited_doc_ids": [1],
            },
            {
                "id": 11,
                "claim": "Claim two.",
                "evidence": {"2": [{"sentences": [0], "label": "CONTRADICT"}]},
                "cited_doc_ids": [2],
            },
            {"id": 12, "claim": "Claim three.", "evidence": {}, "cited_doc_ids": []},
        ],
    )

    gold = load_gold(claims, corpus)

    assert [item.gold_verdict for item in gold] == [Verdict.SUPPORTED, Verdict.REFUTED, Verdict.INSUFFICIENT]
    assert gold[0].claim_id == "10"
    assert gold[0].abstracts[0].title == "Paper One"
    assert gold[0].abstracts[0].abstract == "A. B."
    assert gold[2].abstracts == []
