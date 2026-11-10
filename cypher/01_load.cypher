// 01_load.cypher — build the grid from CSVs in /import
// Run the whole file in Neo4j Browser (multi-statement is on by default) or
//   cat cypher/01_load.cypher | docker exec -i neo4j-statbytes cypher-shell -u neo4j -p statbytes2026

// ---- start clean (safe to re-run) --------------------------------------------
MATCH (n) DETACH DELETE n;

// ---- constraints: uniqueness + an index for free -----------------------------
CREATE CONSTRAINT sub_id  IF NOT EXISTS FOR (s:Substation) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT gen_id  IF NOT EXISTS FOR (g:Generator)  REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT load_id IF NOT EXISTS FOR (l:Load)       REQUIRE l.id IS UNIQUE;

// ---- nodes -------------------------------------------------------------------
LOAD CSV WITH HEADERS FROM 'file:///substations.csv' AS row
CREATE (:Substation {
  id: row.id, name: row.name,
  voltage_kv: toInteger(row.voltage_kv), region: row.region,
  online: toBoolean(row.online),
  lat: toFloat(row.lat), lon: toFloat(row.lon),
  location: point({latitude: toFloat(row.lat), longitude: toFloat(row.lon)})
});

LOAD CSV WITH HEADERS FROM 'file:///generators.csv' AS row
CREATE (:Generator {
  id: row.id, name: row.name, type: row.type,
  capacity_mw: toInteger(row.capacity_mw), marginal_cost: toFloat(row.marginal_cost),
  online: toBoolean(row.online),
  lat: toFloat(row.lat), lon: toFloat(row.lon)
});

LOAD CSV WITH HEADERS FROM 'file:///loads.csv' AS row
CREATE (:Load {
  id: row.id, name: row.name, kind: row.kind,
  demand_mw: toInteger(row.demand_mw),
  lat: toFloat(row.lat), lon: toFloat(row.lon)
});

// ---- relationships -----------------------------------------------------------
LOAD CSV WITH HEADERS FROM 'file:///lines.csv' AS row
MATCH (a:Substation {id: row.from_id}), (b:Substation {id: row.to_id})
CREATE (a)-[:LINE {
  capacity_mw: toInteger(row.capacity_mw), length_km: toFloat(row.length_km),
  fault_prob: toFloat(row.fault_prob), voltage_kv: toInteger(row.voltage_kv)
}]->(b);

LOAD CSV WITH HEADERS FROM 'file:///feeds.csv' AS row
MATCH (g:Generator {id: row.gen_id}), (s:Substation {id: row.sub_id})
CREATE (g)-[:FEEDS {capacity_mw: toInteger(row.capacity_mw)}]->(s);

LOAD CSV WITH HEADERS FROM 'file:///supplies.csv' AS row
MATCH (s:Substation {id: row.sub_id}), (l:Load {id: row.load_id})
CREATE (s)-[:SUPPLIES]->(l);

// ---- derived edge weight for "safest path": -log(1 - p) is additive -----------
MATCH ()-[r:LINE]->() SET r.risk = -log(1 - r.fault_prob);

// ---- check ---------------------------------------------------------------------
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;
