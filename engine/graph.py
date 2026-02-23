"""
engine/graph.py
Production chain graph traversal engine.

Build a directed graph from Placed_Nodes + Connections, then calculate
the actual items/min flowing through each node and connection, and
detect deficits or surpluses.
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class NodeResult:
    """Computed production data for one placed node."""
    node_id: int
    machine_name: str
    recipe_name: str | None
    output_rate: float          # Main items/min produced
    inputs: list[dict]          # List of {"material": str, "rate": float}
    status: str                 # "ok" | "no_recipe" | "disconnected"

    @property
    def total_input_rate(self) -> float:
        return sum(i["rate"] for i in self.inputs)


@dataclass
class ConnectionResult:
    """Computed flow data for one belt/pipe connection."""
    connection_id: int
    source_node_id: int
    target_node_id: int
    material_name: str | None
    flow_rate: float            # items/min carried
    capacity: float             # items/min the source can produce
    status: str                 # "ok" | "deficit" | "surplus"


@dataclass
class GraphResult:
    """Full result returned by calculate_production()."""
    nodes: dict[int, NodeResult] = field(default_factory=dict)
    connections: dict[int, ConnectionResult] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(placed_nodes: list[dict],
                connections: list[dict]) -> dict:
    """
    Convert flat DB rows into an adjacency structure.

    Returns:
        {
          "nodes": { node_id: placed_node_dict, ... },
          "adjacency": { node_id: [connection_dict, ...], ... },   # outgoing edges
          "connections": { conn_id: connection_dict, ... },
        }
    """
    graph: dict = {
        "nodes": {},
        "adjacency": {},
        "connections": {},
    }

    for node in placed_nodes:
        nid = node["id"]
        graph["nodes"][nid] = node
        graph["adjacency"][nid] = []

    for conn in connections:
        cid = conn["id"]
        graph["connections"][cid] = conn
        src = conn["source_node_id"]
        if src in graph["adjacency"]:
            graph["adjacency"][src].append(conn)

    return graph


# ---------------------------------------------------------------------------
# Production calculator
# ---------------------------------------------------------------------------

def calculate_production(
    graph: dict,
    recipes: list[dict],
    machines: list[dict],
    materials: list[dict],
) -> GraphResult:
    """
    Traverse the graph and compute output/input rates and connection statuses.

    Args:
        graph:     Output of build_graph().
        recipes:   All recipe rows from the DB.
        machines:  All machine rows from the DB.
        materials: All material rows from the DB.

    Returns:
        GraphResult with per-node and per-connection data.
    """
    recipe_map:   dict[int, dict] = {r["id"]: r for r in recipes}
    machine_map:  dict[int, dict] = {m["id"]: m for m in machines}
    material_map: dict[int, dict] = {m["id"]: m for m in materials}

    result = GraphResult()

    # --- Compute per-node output rates ---
    node_output_rate: dict[int, float] = {}   # node_id → items/min produced

    for node_id, node in graph["nodes"].items():
        machine = machine_map.get(node["machine_id"])
        machine_name = machine["name"] if machine else "Unknown"

        recipe_id = node.get("recipe_id")
        recipe = recipe_map.get(recipe_id) if recipe_id else None

        # Determine if this is a logistics node (Merger/Splitter)
        is_logistics = "Merger" in machine_name or "Splitter" in machine_name

        if recipe is None:
            # Logistics nodes are "OK" even without a recipe
            status = "ok" if is_logistics else "no_recipe"
            result.nodes[node_id] = NodeResult(
                node_id=node_id,
                machine_name=machine_name,
                recipe_name=None,
                output_rate=0.0,
                inputs=[],
                status=status,
            )
            node_output_rate[node_id] = 0.0
            continue

        # ... rest of node processing ...
        clock_speed = node.get("clock_speed", 1.0)
        craft_time  = recipe["craft_time"]          # seconds per cycle

        items = recipe.get("materials", [])
        input_list = []
        node_output_rate[node_id] = 0.0

        for item in items:
            rate = (item["amount"] / craft_time) * 60.0 * clock_speed
            if item["is_input"]:
                input_list.append({"material": item["material_name"], "rate": rate})
            else:
                node_output_rate[node_id] += rate

        result.nodes[node_id] = NodeResult(
            node_id=node_id,
            machine_name=machine_name,
            recipe_name=recipe["name"],
            output_rate=round(node_output_rate[node_id], 4),
            inputs=input_list,
            status="ok",
        )

    # --- Pass-through Flow Propagation (Logistics) ---
    # We do multiple passes to propagate flow through Mergers/Splitters
    for _ in range(5):
        # Reset logistics outputs for this pass
        logistics_acc = {} # node_id -> accumulated flow
        
        # Calculate outgoing flow for each connection
        out_counts = {nid: len(adj) for nid, adj in graph["adjacency"].items()}
        
        for conn_id, conn in graph["connections"].items():
            src_id = conn["source_node_id"]
            tgt_id = conn["target_node_id"]
            
            total_src_rate = node_output_rate.get(src_id, 0.0)
            num_conns      = out_counts.get(src_id, 1)
            src_rate       = total_src_rate / num_conns if num_conns > 0 else 0.0
            
            # If target is logistics, accumulate
            tgt_node = graph["nodes"].get(tgt_id)
            if tgt_node:
                tgt_mach = machine_map.get(tgt_node["machine_id"])
                if tgt_mach and ("Merger" in tgt_mach["name"] or "Splitter" in tgt_mach["name"]):
                    logistics_acc[tgt_id] = logistics_acc.get(tgt_id, 0.0) + src_rate

        # Apply accumulated flow to logistics node outputs for next pass
        changed = False
        for nid, acc_rate in logistics_acc.items():
            if round(node_output_rate.get(nid, 0.0), 4) != round(acc_rate, 4):
                node_output_rate[nid] = acc_rate
                result.nodes[nid].output_rate = round(acc_rate, 4)
                changed = True
        if not changed: break

    # --- Compute final per-connection results ---
    out_counts = {nid: len(adj) for nid, adj in graph["adjacency"].items()}
    for conn_id, conn in graph["connections"].items():
        src_id = conn["source_node_id"]
        tgt_id = conn["target_node_id"]

        total_src_rate = node_output_rate.get(src_id, 0.0)
        num_conns      = out_counts.get(src_id, 1)
        src_rate       = total_src_rate / num_conns if num_conns > 0 else 0.0

        tgt_node_r = result.nodes.get(tgt_id)
        demand     = tgt_node_r.total_input_rate if tgt_node_r else 0.0

        # Dynamic Material Detection
        mat_name = None
        if conn.get("material_id"):
            mat = material_map.get(conn["material_id"])
            if mat: mat_name = mat["name"]
        
        if not mat_name:
            # Guess from source node output
            src_nr = result.nodes.get(src_id)
            if src_nr and src_nr.recipe_name:
                # If source has recipe, pick the first output material
                src_recipe_id = graph["nodes"][src_id].get("recipe_id")
                src_recipe = recipe_map.get(src_recipe_id)
                if src_recipe and "materials" in src_recipe:
                    outputs = [m for m in src_recipe["materials"] if not m["is_input"]]
                    if outputs:
                        mat_name = outputs[0]["material_name"]
            elif src_nr and ("Merger" in src_nr.machine_name or "Splitter" in src_nr.machine_name):
                # Logistics nodes don't have recipes, but we could propagate name too... 
                # (For now, let's keep it simple: if no explicit mat, use source recipe)
                pass

        # Find specific demand for this material at the target
        demand = 0.0
        if tgt_node_r:
            for inp in tgt_node_r.inputs:
                if inp["material"] == mat_name:
                    demand = inp["rate"]
                    break

        if mat_name and src_rate < demand - 0.001:
            status = "deficit"
        elif mat_name and src_rate > demand + 0.001:
            status = "surplus"
        else:
            status = "ok"

        result.connections[conn_id] = ConnectionResult(
            connection_id=conn_id,
            source_node_id=src_id,
            target_node_id=tgt_id,
            material_name=mat_name,
            flow_rate=round(src_rate, 4),
            capacity=round(total_src_rate, 4),
            status=status,
        )

    return result


# ---------------------------------------------------------------------------
# Pretty printer (for CLI use)
# ---------------------------------------------------------------------------

def print_results(result: GraphResult) -> None:
    print("\n" + "=" * 60)
    print("  PRODUCTION CHAIN ANALYSIS")
    print("=" * 60)

    print("\n[NODES]")
    for nr in result.nodes.values():
        status_icon = {"ok": "[OK]  ", "no_recipe": "[WARN]", "disconnected": "[DISC]"}.get(nr.status, "[?]")
        print(f"  {status_icon} Node {nr.node_id} -- {nr.machine_name}")
        if nr.recipe_name:
            print(f"       Recipe  : {nr.recipe_name}")
            print(f"       Produces: {nr.output_rate} items/min")
            for inp in nr.inputs:
                print(f"       Consumes: {inp['rate']} {inp['material']}/min")
        else:
            print("       (no recipe assigned)")

    print("\n[CONNECTIONS]")
    for cr in result.connections.values():
        status_icon = {"ok": "[OK]    ", "deficit": "[DEFICIT]", "surplus": "[SURPLUS]"}.get(cr.status, "[?]")
        mat = cr.material_name or "unknown material"
        print(
            f"  {status_icon} Connection {cr.connection_id}: "
            f"Node {cr.source_node_id} -> Node {cr.target_node_id}  "
            f"| {mat}  | {cr.flow_rate} items/min  | {cr.status.upper()}"
        )

    print("=" * 60 + "\n")
