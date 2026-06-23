"""Configuration constants for the verdict pipeline: service wiring and calibration."""

# Embeddings service (TEI) endpoint path; the host is injected per deployment.
EMBEDDINGS_EMBED_PATH = "/embed"

# HelixDB v3 local instance (Docker container, on-disk). Queries are dynamic.
# Node labels are PascalCase; properties and edge labels mirror the domain model.
HELIX_URL = "http://localhost:6969"
HELIX_PAPER_LABEL = "Paper"
HELIX_EMBEDDING_FIELD = "embedding"

# A paper counts as foundational only above this citation floor (loose v1 default).
FOUNDATION_MIN_CITED = 10

# Max per-paper LLM stance calls per claim; excess papers are dropped lowest-weight first.
MAX_STANCE_CALLS = 30

# Evidence influence is recency-weighted: an item one half-life older counts half.
# These are loose v1 defaults, calibrated on the gold set.
CURRENT_YEAR = 2026
RECENCY_HALF_LIFE_YEARS = 8

# Confidence band cut-points on |weighted_lean| (the evidence-balance base).
CONFIDENCE_HIGH_MIN = 0.6
CONFIDENCE_MODERATE_MIN = 0.3

# Kendall's W below this floor marks the verdict unsettled and caps the band one step.
KENDALLS_W_UNSETTLED_FLOOR = 0.4

# Cheap-pass self-uncertainty at/above this floor caps the confidence band one step.
SELF_UNCERTAINTY_CAP_FLOOR = 0.5
