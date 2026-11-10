// 02_basics.cypher — the Cypher tutorial, in presentation order.
// Run ONE block at a time in Neo4j Browser (or from demo.ipynb).

// Q1. What's in the database?  Counts by label and by relationship type.
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;

MATCH ()-[r]->() RETURN type(r) AS relationship, count(*) AS n ORDER BY n DESC;


// Q2. Look up one node.  (Compare: SELECT * FROM substation WHERE name = 'Allegheny-01')
MATCH (s:Substation {name: 'Allegheny-01'})
RETURN s;


// Q3. One hop out: the lines and neighbours of that substation.
//     Switch the result panel to graph view.
MATCH p = (s:Substation {name: 'Allegheny-01'})-[:LINE]-(t:Substation)
RETURN p;


// Q4. A longer pattern: a nuclear plant, its substation, and the substations one line away.
MATCH p = (g:Generator {type: 'nuclear'})-[:FEEDS]->(:Substation)-[:LINE]-(:Substation)
RETURN p;


// Q5. Filter and aggregate: online generation vs demand, by region.
MATCH (g:Generator)-[:FEEDS]->(s:Substation)
WHERE g.online
WITH s.region AS region, sum(g.capacity_mw) AS generation_mw
MATCH (t:Substation {region: region})-[:SUPPLIES]->(l:Load)
RETURN region, generation_mw, sum(l.demand_mw) AS demand_mw
ORDER BY region;


// Q6. Variable-length paths: hospitals within 3 lines of a nuclear plant.
MATCH (g:Generator {type: 'nuclear'})-[:FEEDS]->(:Substation)-[:LINE*1..3]-(s:Substation)
      -[:SUPPLIES]->(h:Load {kind: 'hospital'})
RETURN DISTINCT g.name AS plant, h.name AS hospital, s.name AS via_substation;


// Q7. Shortest path between two distant substations (unweighted, built in).
MATCH (a:Substation {name: 'Allegheny-01'}), (b:Substation {name: 'Pocono-01'})
MATCH p = shortestPath((a)-[:LINE*]-(b))
RETURN length(p) AS hops, [n IN nodes(p) | n.name] AS route;


// Q8. A write: change a property.  Same pattern syntax.
MATCH (s:Substation {name: 'Allegheny-01'})
SET s.inspected = date()
RETURN s.name, s.inspected;
