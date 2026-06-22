"""Configuration constants for the verdict pipeline: service wiring and calibration."""

# Embeddings service (TEI) endpoint path; the host is injected per deployment.
EMBEDDINGS_EMBED_PATH = "/embed"

# Evidence influence is recency-weighted: an item one half-life older counts half.
# These are loose v1 defaults, calibrated on the gold set.
CURRENT_YEAR = 2026
RECENCY_HALF_LIFE_YEARS = 8

# Confidence band cut-points on |weighted_lean| (the evidence-balance base).
CONFIDENCE_HIGH_MIN = 0.6
CONFIDENCE_MODERATE_MIN = 0.3

# Kendall's W below this floor marks the verdict unsettled and caps the band one step.
KENDALLS_W_UNSETTLED_FLOOR = 0.4
