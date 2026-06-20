"""Tests for the shared vector math helpers."""

import pytest
from verdict.vectors import cosine_similarity


def test_cosine_similarity_is_one_for_identical_vectors():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_is_zero_for_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_is_minus_one_for_opposite_vectors():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_is_zero_when_either_vector_is_zero_norm():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
