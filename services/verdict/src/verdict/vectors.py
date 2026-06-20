"""Shared vector math helpers."""

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity of two vectors.

    Parameters
    ----------
    a : list[float]
        The first vector.
    b : list[float]
        The second vector.

    Returns
    -------
    float
        The cosine similarity, or 0.0 if either vector is zero-norm.
    """
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    norm = float(np.linalg.norm(va)) * float(np.linalg.norm(vb))
    if norm == 0.0:
        return 0.0
    return float(np.dot(va, vb) / norm)
