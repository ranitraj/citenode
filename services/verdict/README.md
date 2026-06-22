# verdict

Give it a factual claim. It finds the relevant research, weighs what the papers
say, and returns a verdict: **supported, contested, refuted, or insufficient**,
with its reasons and the papers it used. The whole point is to **refuse to fake
agreement**, so it goes looking for work that disagrees.

---

## The big picture

```
┌───────┐   ┌────────┐   ┌────────┐   ┌───────┐   ┌─────────┐
│ claim │──▶│ triage │──▶│ gather │──▶│ judge │──▶│ verdict │
└───────┘   └────────┘   └────────┘   └───────┘   └─────────┘
```

- **triage**: is this a real, checkable claim? Vague or loaded ones go back for a
  rewrite instead of an answer.
- **gather**: find the relevant papers and what each one says (below).
- **judge**: one quick model for easy claims, a council of models for hard ones.
  When the models disagree, confidence goes *down*, it is never hidden.
- **verdict**: the four-way answer, the reasoning, any disagreement, and the
  real papers behind it.

---

## How evidence is gathered

Start from the claim, find a few seed papers, fetch each one in full, then walk
the citation graph **both ways**. Four steps:

```
             ┌───────────────────┐
             │       claim       │
             └─────────┬─────────┘
                       │ search_seeds
                       ▼
             ┌───────────────────┐
             │    seed papers    │
             └─────────┬─────────┘
                       │ fetch_work
                       ▼
             ┌───────────────────┐
             │    full paper     │
             └─────────┬─────────┘
          ┌────────────┴────────────┐
          ▼                         ▼
┌────────────────────┐    ┌────────────────────┐
│ outgoing_refs      │    │ incoming_citations │
│ what it cites      │    │ who cites it       │
│ (foundations)      │    │ (challengers)      │
└─────────┬──────────┘    └─────────┬──────────┘
          └────────────┬────────────┘
                       ▼
             ┌───────────────────┐
             │  graph + vector   │
             │       store       │
             └───────────────────┘
```

- **`search_seeds`**: search for the papers most relevant to the claim.
- **`fetch_work`**: pull one paper in full (title, year, abstract, retracted
  flag, venue) and rebuild its abstract (see below).
- **`outgoing_refs`**: the papers it cites, the work it builds on.
- **`incoming_citations`**: the papers that cite it, where pushback lives.

**Why both ways?** A challenge to a study is almost never in its own reference
list: a study can only cite earlier work, and challenges come later. They show up
in the papers that *cite it*. But citing is not the same as disagreeing, so we
pull `incoming_citations` to make disagreement reachable, then read each paper to
see if it actually pushes back.

---

## Things worth knowing

- **Abstracts arrive scrambled.** The research index cannot share plain abstract
  text, so it sends each abstract as a word-to-positions map. We rebuild the text.
  Many older papers have none, so we store a blank and flag it later.
- **A citation has no opinion.** The graph only says "paper A cites paper B", not
  whether A agrees. So stance (supports / contradicts / neutral / off-topic) is
  decided by a model reading the abstract, never read off the graph.
- **Retracted papers are tracked, not dropped quietly.** We carry a retracted flag
  so they can be left out of the verdict on purpose.
- **One store, two jobs.** Papers sit in one graph + vector store. A single step
  can find papers close in meaning to the claim and then walk their citations:
  semantic search and graph traversal together, not two systems glued up.

---

## How it's put together

The core logic talks to a few swappable boundaries: where papers come from, where
they are stored, how text is embedded, and which models to use. Each one can
change without touching the logic.

| Boundary             | What it does                          | Today          |
| -------------------- | ------------------------------------- | -------------- |
| literature source    | find and fetch papers                 | built          |
| graph + vector store | store papers, embeddings, citations   | in-memory only |
| paper embeddings     | turn papers into vectors for recall   | adapter built  |
| text embeddings      | compare model answers for agreement   | adapter built  |
| model provider       | the models for triage, judging, panel | planned        |

---

## Run

```bash
# from services/verdict
uv run pytest -q     # tests (offline, the research source is mocked)
make lint            # ruff + mypy + pylint (from repo root)
```

## Deeper docs

The design notes and decision records under [`.claude/`](../../.claude/) explain
why.
