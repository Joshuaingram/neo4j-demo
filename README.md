# A Crash Course in Graph Databases with neo4j — demo repo

StatBytes, CMU Statistics & Data Science, Nov 4 2026 — Joshua Ingram

A synthetic regional power grid (140 substations, 322 lines, 25 generators, 60 loads)
stored in neo4j, queried with Cypher, analysed with the Graph Data Science library.

```
demo/
  docker-compose.yml      neo4j 5 + GDS plugin; password statbytes2026; ./data mounted at /import
  make_data.py            regenerates the synthetic grid (seeded) into data/
  offline_figures.py      slide figures + fallback_results.md via networkx (no neo4j needed)
  data/*.csv              substations, lines, generators, feeds, loads, supplies
  cypher/01_load.cypher   constraints + LOAD CSV
  cypher/02_basics.cypher the Cypher tutorial, 8 queries in order
  cypher/03_gds.cypher    projection → degree → eigenvector → betweenness → components after an outage
  demo.ipynb              the same queries from Python (every call returns a DataFrame)
  DEMO_STEPS.md           what to paste, say, and expect, step by step
  figures/                PDFs used in the slides
```

## Setup, option A: Docker (recommended, ~2 minutes)

```bash
docker compose up -d            # first start downloads the GDS plugin (~1 min)
docker compose logs -f neo4j    # wait for "Started."
```

Open <http://localhost:7474>, log in with `neo4j` / `statbytes2026`, paste the contents
of `cypher/01_load.cypher` into the editor and run it. You should see counts:
Substation 140, Load 60, Generator 25.

Or from the shell:

```bash
cat cypher/01_load.cypher | docker exec -i neo4j-statbytes cypher-shell -u neo4j -p statbytes2026
```

Stop / reset:

```bash
docker compose down          # keeps the database volume
docker compose down -v       # deletes it
```

## Setup, option B: Neo4j Desktop (no Docker)

1. Install Neo4j Desktop from <https://neo4j.com/download/>.
2. Create a project → **Add → Local DBMS** (version 5.x), password `statbytes2026`.
3. Select the DBMS → **Plugins** tab → install **Graph Data Science Library**.
4. Click the `...` menu → **Open folder → Import**, and copy everything in `data/` there.
5. Start the DBMS, open Neo4j Browser, run `cypher/01_load.cypher`.

Note: Neo4j **Aura Free** (the hosted tier) does *not* include GDS; you'd need AuraDS.

## Python

```bash
pip install graphdatascience neo4j pandas matplotlib networkx jupyter
jupyter lab demo.ipynb
```

## Graph model

```
(:Generator  {id, name, type, capacity_mw, marginal_cost, online, lat, lon})
(:Substation {id, name, voltage_kv, region, online, lat, lon, location})
(:Load       {id, name, kind, demand_mw, lat, lon})

(:Generator)-[:FEEDS {capacity_mw}]->(:Substation)
(:Substation)-[:LINE {capacity_mw, length_km, fault_prob, voltage_kv, risk}]->(:Substation)
(:Substation)-[:SUPPLIES]->(:Load)
```

`fault_prob` is an annual probability that the line trips. `risk = -log(1 - fault_prob)` is also
stored (additive along a path) for weighted shortest-path experiments.

## Versions this was written against

Written against the Neo4j 5 LTS Docker image (`neo4j:5`, which auto-installs a compatible GDS) and `graphdatascience` client 1.x; procedure names were checked against the Nov 2026 docs (latest server is `neo4j:2026.10`, GDS 2026.10, `neo4j-graphrag` 1.22). Dijkstra uses `targetNodes: [...]` (the singular `targetNode` is deprecated).
If a procedure name has changed, `CALL gds.list()` shows what your GDS has.
