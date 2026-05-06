# Mapping Recent A* Research Relevant to Verified Neuro-Symbolic Knowledge Graph Repair

This project builds a curated literature map of recent papers from ICORE A* conferences that are most relevant to my PhD research on verified neuro-symbolic knowledge graph repair. Starting from a core set of top venues in AI, machine learning, knowledge representation, data management, and Web research, the project collects papers from the last three years and ranks them by relevance to themes such as knowledge graphs, constraints, data repair, graph neural networks, LLM agents, symbolic validation, and benchmark construction. The final output will be a structured shortlist of must-read papers, organized by research theme, to support positioning, related work analysis, and future publication planning.

# Implementation Plan

Use a **two-stage pipeline**:

1. **Harvest papers from the Core A* venues**
2. **Rank/filter them by semantic relatedness to your PhD topic**

Do not start by manually searching Google Scholar. You will miss papers and introduce bias.

## 1. Define the venue set

Use the following ICORE A* conferences list:

```text
KR, AAAI, IJCAI,
NeurIPS, ICLR, ICML,
KDD, WWW,
SIGMOD, VLDB, PODS, ICDE
```

For “last 3 years,” I would use:

```text
2023, 2024, 2025, 2026-so-far
```

Since today is **May 6, 2026**, many 2026 proceedings may not be complete yet.

## 2. Use DBLP to get the venue-year paper lists

DBLP is the best starting point for **canonical CS bibliography metadata**. Its API exposes publication, author, and venue search services. ([dblp.org][1])

Use DBLP to get:

```text
title
authors
year
venue
DOI / URL
DBLP key
```

But DBLP is usually not enough for semantic filtering because it often lacks abstracts.

## 3. Enrich each paper with abstracts and citation metadata

For each DBLP paper, query:

### Semantic Scholar

Use it to retrieve:

```text
abstract
fieldsOfStudy
citationCount
influentialCitationCount
references
citations
TLDR, when available
```

Semantic Scholar’s Graph API is explicitly designed for paper search, citation traversal, and paper metadata retrieval. ([Semantic Scholar][2])

### OpenAlex

Use it as a second metadata source, especially for:

```text
abstract_inverted_index
concepts
cited_by_count
open access links
publication date
```

OpenAlex supports filtering works by dates and other work fields, including `from_publication_date` and `to_publication_date`. ([developers.openalex.org][3])

### OpenReview

Use this mainly for:

```text
ICLR
NeurIPS
some workshop-style or open-review venues
```

OpenReview is relevant because many ML venues use it for submissions, reviews, and accepted paper metadata. ([docs.openreview.net][4])

## 4. Build a relatedness rubric

For your research, I would score each paper along these axes:

| Axis                                           |                                                                                   Description | Weight |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------: | -----: |
| **KG / RDF / Wikidata relevance**              |                     Knowledge graphs, RDF, Wikidata, KG completion, KG editing, semantic data |      3 |
| **Repair / constraint / validation relevance** |     Data repair, constraint violations, consistency, SHACL-like validation, symbolic checking |      3 |
| **Neuro-symbolic relevance**                   |                     Logic + neural models, verifier-guided learning, differentiable reasoning |      2 |
| **Graph ML relevance**                         |                           GNNs, graph representation learning, KG embeddings, message passing |      2 |
| **LLM-agent relevance**                        |                        LLMs for KG reasoning, tool use, retrieval, verification, data editing |      2 |
| **Database/data quality relevance**            | Integrity constraints, data cleaning, entity resolution, provenance, inconsistency management |      2 |
| **Benchmark/evaluation relevance**             |               Real-world KG benchmarks, edit histories, temporal evaluation, symbolic metrics |      2 |

Then compute a score from title + abstract + keywords.

Example:

```text
score = 
  3 * KG_related
+ 3 * repair_constraint_related
+ 2 * neurosymbolic_related
+ 2 * graph_ml_related
+ 2 * llm_agent_related
+ 2 * data_quality_related
+ 2 * benchmark_related
```

Keep papers above a threshold, e.g.:

```text
score >= 5  → relevant
score >= 8  → highly relevant
score >= 11 → must-read
```

## 5. Use targeted query terms

Use these as positive keywords:

```text
knowledge graph
Wikidata
RDF
semantic web
ontology
KG completion
KG embeddings
graph neural network
GNN
message passing
neuro-symbolic
symbolic reasoning
constraints
integrity constraints
constraint violation
data repair
knowledge graph repair
data cleaning
fact verification
entity resolution
provenance
SHACL
RDF validation
LLM agent
tool-augmented LLM
verifier-guided
retrieval-augmented
```

Use these as negative or low-priority filters:

```text
image classification
object detection
robotics
hardware
networking
cryptography
pure recommender systems
pure NLP without KG/reasoning
pure theory without data/constraint angle
```

## 6. Practical workflow

I would do this as a spreadsheet or CSV pipeline.

Columns:

```text
year
venue
title
authors
abstract
url
doi
citation_count
source
kg_score
repair_score
neurosymbolic_score
graph_ml_score
llm_score
data_quality_score
benchmark_score
total_score
reason_for_inclusion
priority
```

Priority values:

```text
A = must read
B = likely useful
C = peripheral
Reject = not relevant
```

## 7. Recommended search strategy by venue family

### KR, AAAI, IJCAI

Look for:

```text
knowledge representation
reasoning
ontology repair
belief revision
neuro-symbolic
constraints
planning for repair
LLM reasoning
```

These are likely to contain your most conceptually aligned papers.

### NeurIPS, ICML, ICLR

Look for:

```text
GNNs
KG embeddings
LLM reasoning
tool use
neuro-symbolic learning
graph foundation models
constraint-aware learning
```

These are method venues. A paper may be relevant even if it does not mention “knowledge graph repair.”

### KDD, WWW, ICDE, SIGMOD, VLDB, PODS

Look for:

```text
data repair
entity resolution
data quality
integrity constraints
graph data management
Wikidata
web-scale knowledge graphs
provenance
database constraints
```

These may be extremely relevant to the **benchmark, data quality, and constraint validation** side of your thesis.

## 8. Best implementation path

The robust version is:

```text
DBLP venue/year scrape
→ Semantic Scholar enrichment
→ OpenAlex fallback enrichment
→ keyword + embedding relatedness scoring
→ manual review of top 100–200 papers
→ export to CSV / Zotero / BibTeX
```

The weaker but faster version is:

```text
Semantic Scholar search queries
→ restrict by venue/year when possible
→ manually inspect top results
```

I would avoid relying only on Semantic Scholar venue filters, because venue names are sometimes inconsistent. DBLP first, enrichment second is cleaner.

## 9. Minimal Python architecture

```text
scripts/
  01_fetch_dblp_core_venues.py
  02_enrich_semantic_scholar.py
  03_enrich_openalex.py
  04_score_relatedness.py
  05_export_shortlist.py

data/
  raw/dblp_core_a_star_2023_2026.jsonl
  enriched/papers_enriched.jsonl
  scored/papers_scored.csv
  final/relevant_papers.csv
  final/relevant_papers.bib
```

## 10. What I would produce at the end

Three outputs:

### 1. Full scored table

All papers from the core venues, scored and filterable.

### 2. Shortlist

Probably around:

```text
30–80 papers
```

depending on how strict you are.

### 3. Reading categories

For your thesis, I would categorize the final shortlist as:

```text
A. KG repair / data repair / constraints
B. GNNs and KG representation learning
C. Neuro-symbolic and verifier-guided learning
D. LLMs for KG reasoning and editing
E. Benchmarks and evaluation methodology
F. Database foundations of repair and consistency
```

The most rigorous approach is not to ask “which papers mention KG repair,” because too few will. Ask instead:

> Which recent A* papers solve adjacent subproblems needed for verified neuro-symbolic KG repair?

That framing will capture much more useful work.

[1]: https://dblp.org/faq/How%2Bto%2Buse%2Bthe%2Bdblp%2Bsearch%2BAPI?utm_source=chatgpt.com "How to use the dblp search API?"
[2]: https://www.semanticscholar.org/product/api%2Ftutorial?utm_source=chatgpt.com "Tutorial | Semantic Scholar Academic Graph API"
[3]: https://developers.openalex.org/guides/filtering?utm_source=chatgpt.com "Filter - OpenAlex Developers"
[4]: https://docs.openreview.net/how-to-guides/data-retrieval-and-modification/how-to-check-the-api-version-of-a-venue?utm_source=chatgpt.com "How to check the API version of a venue"
