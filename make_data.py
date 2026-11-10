"""
make_data.py — generate a synthetic regional power grid for the StatBytes neo4j demo.

Writes CSVs to ./data (loaded into neo4j with cypher/01_load.cypher) and
figures to ./figures (used in the slides). Fully seeded; re-running gives
identical output.

Graph model
  (:Generator  {id, name, type, capacity_mw, marginal_cost, online, lat, lon})
  (:Substation {id, name, voltage_kv, region, online, lat, lon})
  (:Load       {id, name, kind, demand_mw, lat, lon})
  (:Generator)-[:FEEDS {capacity_mw}]->(:Substation)
  (:Substation)-[:LINE {capacity_mw, length_km, fault_prob, voltage_kv}]->(:Substation)
  (:Substation)-[:SUPPLIES]->(:Load)

Five regional sub-grids with sparse 345 kV inter-ties, so community detection
and connected-components-after-failure give interpretable results.
"""
import math
import os
import numpy as np
import pandas as pd
import networkx as nx

SEED = 20261104
rng = np.random.default_rng(SEED)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FIGS = os.path.join(HERE, "figures")
os.makedirs(DATA, exist_ok=True)
os.makedirs(FIGS, exist_ok=True)

# ----------------------------------------------------------------------------
# Regions: fictional, laid out roughly like a mid-sized state
# ----------------------------------------------------------------------------
REGIONS = {
    "Allegheny":   dict(lat=40.45, lon=-80.00, n=32),
    "Laurel":      dict(lat=40.25, lon=-78.90, n=26),
    "Susquehanna": dict(lat=40.95, lon=-77.60, n=30),
    "Pocono":      dict(lat=41.05, lon=-75.90, n=28),
    "Erie":        dict(lat=41.90, lon=-79.60, n=24),
}
# which regions are neighbours (inter-ties go between these)
ADJACENT = [("Allegheny", "Laurel"), ("Allegheny", "Erie"), ("Laurel", "Susquehanna"),
            ("Susquehanna", "Pocono"), ("Erie", "Susquehanna")]


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ----------------------------------------------------------------------------
# Substations
# ----------------------------------------------------------------------------
subs = []
sid = 0
for region, cfg in REGIONS.items():
    n = cfg["n"]
    lats = rng.normal(cfg["lat"], 0.18, n)
    lons = rng.normal(cfg["lon"], 0.28, n)
    # voltage tiers: ~3 at 345 kV, ~30% at 138 kV, rest 69 kV
    tiers = np.array([345] * 3 + [138] * int(0.3 * n) + [69] * (n - 3 - int(0.3 * n)))
    rng.shuffle(tiers)
    for i in range(n):
        sid += 1
        subs.append(dict(
            id=f"S{sid:03d}",
            name=f"{region}-{i + 1:02d}",
            voltage_kv=int(tiers[i]),
            region=region,
            online=True,
            lat=round(float(lats[i]), 4),
            lon=round(float(lons[i]), 4),
        ))
subs = pd.DataFrame(subs)

# ----------------------------------------------------------------------------
# Lines: within each region, MST (guarantees connectivity) + extra kNN edges;
# between adjacent regions, 1–2 long 345 kV inter-ties.
# ----------------------------------------------------------------------------
FAULT_RATE_PER_KM = {345: 0.0006, 138: 0.0015, 69: 0.0030}   # annual
CAPACITY = {345: 1500, 138: 400, 69: 120}


def line_props(a, b):
    v = min(a.voltage_kv, b.voltage_kv)
    length = haversine_km(a.lat, a.lon, b.lat, b.lon)
    cap = int(CAPACITY[v] * rng.uniform(0.8, 1.2))
    # annual probability the line trips: 1 - exp(-rate * length), plus a floor
    p = 1 - math.exp(-FAULT_RATE_PER_KM[v] * length) + 0.01
    return dict(capacity_mw=cap, length_km=round(length, 1),
                fault_prob=round(float(p), 4), voltage_kv=v)


edges = {}
for region in REGIONS:
    r = subs[subs.region == region].reset_index(drop=True)
    G = nx.Graph()
    for i, a in r.iterrows():
        for j, b in r.iterrows():
            if i < j:
                G.add_edge(a.id, b.id, w=haversine_km(a.lat, a.lon, b.lat, b.lon))
    mst = nx.minimum_spanning_tree(G, weight="w")
    for u, v in mst.edges():
        edges[tuple(sorted((u, v)))] = None
    # add extra short edges (k-nearest style) for redundancy
    by_id = {row.id: row for _, row in r.iterrows()}
    for _, a in r.iterrows():
        dists = sorted(((haversine_km(a.lat, a.lon, b.lat, b.lon), b.id)
                        for _, b in r.iterrows() if b.id != a.id))
        for d, bid in dists[:4]:
            if rng.uniform() < 0.7:
                edges[tuple(sorted((a.id, bid)))] = None

# inter-ties between 345 kV substations of adjacent regions
by_id = {row.id: row for _, row in subs.iterrows()}
for ra, rb in ADJACENT:
    A = subs[(subs.region == ra) & (subs.voltage_kv == 345)]
    B = subs[(subs.region == rb) & (subs.voltage_kv == 345)]
    pairs = sorted(((haversine_km(a.lat, a.lon, b.lat, b.lon), a.id, b.id)
                    for _, a in A.iterrows() for _, b in B.iterrows()))
    n_ties = 2 if (ra, rb) in [("Allegheny", "Laurel"), ("Susquehanna", "Pocono")] else 1
    for d, u, v in pairs[:n_ties]:
        edges[tuple(sorted((u, v)))] = None

lines = []
for (u, v) in edges:
    props = line_props(by_id[u], by_id[v])
    lines.append(dict(from_id=u, to_id=v, **props))
lines = pd.DataFrame(lines)

# ----------------------------------------------------------------------------
# Generators: attach to 345/138 kV substations
# ----------------------------------------------------------------------------
GEN_TYPES = [
    # type, count, capacity range, marginal cost range ($/MWh)
    ("nuclear", 2, (900, 1200), (9, 12)),
    ("gas", 8, (250, 650), (35, 65)),
    ("hydro", 3, (80, 300), (4, 8)),
    ("wind", 7, (50, 220), (0, 1)),
    ("solar", 5, (20, 110), (0, 1)),
]
hv = subs[subs.voltage_kv >= 138]
gens, feeds = [], []
gid = 0
for gtype, count, cap_rng, cost_rng in GEN_TYPES:
    for k in range(count):
        gid += 1
        s = hv.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        cap = int(rng.uniform(*cap_rng))
        gens.append(dict(
            id=f"G{gid:02d}",
            name=f"{gtype.capitalize()}-{k + 1:02d}",
            type=gtype,
            capacity_mw=cap,
            marginal_cost=round(float(rng.uniform(*cost_rng)), 1),
            online=bool(rng.uniform() > 0.08),
            lat=round(float(s.lat + rng.normal(0, 0.03)), 4),
            lon=round(float(s.lon + rng.normal(0, 0.04)), 4),
        ))
        feeds.append(dict(gen_id=f"G{gid:02d}", sub_id=s.id, capacity_mw=cap))
gens = pd.DataFrame(gens)
feeds = pd.DataFrame(feeds)

# ----------------------------------------------------------------------------
# Loads: attach to 69/138 kV substations
# ----------------------------------------------------------------------------
LOAD_KINDS = [
    ("residential", 38, (20, 90)),
    ("industrial", 16, (60, 220)),
    ("hospital", 6, (5, 20)),
]
lv = subs[subs.voltage_kv <= 138]
loads, supplies = [], []
lid = 0
for kind, count, dem_rng in LOAD_KINDS:
    for k in range(count):
        lid += 1
        s = lv.sample(1, random_state=int(rng.integers(1e9))).iloc[0]
        loads.append(dict(
            id=f"L{lid:02d}",
            name=f"{kind.capitalize()}-{k + 1:02d}",
            kind=kind,
            demand_mw=int(rng.uniform(*dem_rng)),
            lat=round(float(s.lat + rng.normal(0, 0.03)), 4),
            lon=round(float(s.lon + rng.normal(0, 0.04)), 4),
        ))
        supplies.append(dict(sub_id=s.id, load_id=f"L{lid:02d}"))
loads = pd.DataFrame(loads)
supplies = pd.DataFrame(supplies)

# ----------------------------------------------------------------------------
# Write CSVs
# ----------------------------------------------------------------------------
for df in (subs, gens):
    df["online"] = df["online"].map(lambda b: "true" if b else "false")
subs.to_csv(os.path.join(DATA, "substations.csv"), index=False)
lines.to_csv(os.path.join(DATA, "lines.csv"), index=False)
gens.to_csv(os.path.join(DATA, "generators.csv"), index=False)
feeds.to_csv(os.path.join(DATA, "feeds.csv"), index=False)
loads.to_csv(os.path.join(DATA, "loads.csv"), index=False)
supplies.to_csv(os.path.join(DATA, "supplies.csv"), index=False)

print(f"substations {len(subs)}  lines {len(lines)}  generators {len(gens)}  "
      f"loads {len(loads)}  feeds {len(feeds)}  supplies {len(supplies)}")
print("voltage tiers:", subs.voltage_kv.value_counts().to_dict())
print("fault_prob range: %.3f – %.3f" % (lines.fault_prob.min(), lines.fault_prob.max()))
