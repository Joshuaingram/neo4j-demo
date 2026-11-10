// 03_gds.cypher — Graph Data Science demo, in presentation order.
// Run one block at a time in Neo4j Browser (or from demo.ipynb).

// G0. Project the substation/line graph into GDS memory.
//     Undirected, with the line properties we might want as weights.
CALL gds.graph.project(
  'grid',
  'Substation',
  { LINE: { orientation: 'UNDIRECTED', properties: ['length_km', 'capacity_mw'] } }
)
YIELD graphName, nodeCount, relationshipCount;


// G1. Degree centrality: how many lines meet at each substation?
CALL gds.degree.stream('grid')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS s, score
RETURN s.name AS substation, s.region AS region, s.voltage_kv AS kv, toInteger(score) AS degree
ORDER BY score DESC, s.name LIMIT 10;


// G2. Eigenvector centrality: connected to substations that are themselves well connected.
CALL gds.eigenvector.stream('grid', { maxIterations: 200 })
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS s, score
RETURN s.name AS substation, s.region AS region, s.voltage_kv AS kv, round(score, 3) AS eigenvector
ORDER BY score DESC LIMIT 10;


// G3. Betweenness centrality: on how many shortest paths does each substation sit?
CALL gds.betweenness.stream('grid')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS s, score
RETURN s.name AS substation, s.region AS region, s.voltage_kv AS kv, round(score) AS betweenness
ORDER BY score DESC LIMIT 10;


// G4. What if a substation broke?  Take the top-betweenness node offline,
//     project only ONLINE substations, and find the connected components.
MATCH (s:Substation {name: 'Susquehanna-27'}) SET s.online = false;

MATCH (s:Substation)-[:LINE]-(t:Substation)
WHERE s.online AND t.online
WITH gds.graph.project('grid_online', s, t) AS g
RETURN g.graphName AS graph, g.nodeCount AS nodes, g.relationshipCount AS relationships;

CALL gds.wcc.stream('grid_online')
YIELD nodeId, componentId
WITH gds.util.asNode(nodeId) AS s, componentId
CALL (s) { MATCH (s)<-[:FEEDS]-(g:Generator) WHERE g.online RETURN sum(g.capacity_mw) AS gen }
CALL (s) { MATCH (s)-[:SUPPLIES]->(l:Load)
       RETURN sum(l.demand_mw) AS dem, sum(CASE WHEN l.kind = 'hospital' THEN 1 ELSE 0 END) AS hosp }
RETURN componentId, count(s) AS substations, collect(DISTINCT s.region) AS regions,
       sum(gen) AS generation_mw, sum(dem) AS demand_mw, sum(hosp) AS hospitals
ORDER BY substations DESC;


// G5. Write a result back to the database, so ordinary Cypher can use it.
CALL gds.betweenness.write('grid', { writeProperty: 'betweenness' })
YIELD nodePropertiesWritten;

MATCH (s:Substation) RETURN s.name, s.region, round(s.betweenness) AS betweenness
ORDER BY s.betweenness DESC LIMIT 5;


// ---- cleanup (run after the demo) -------------------------------------------
// CALL gds.graph.drop('grid');  CALL gds.graph.drop('grid_online');
// MATCH (s:Substation) SET s.online = true;
