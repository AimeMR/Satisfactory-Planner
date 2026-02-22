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

        if recipe is None:
            result.nodes[node_id] = NodeResult(
                node_id=node_id,
                machine_name=machine_name,
                recipe_name=None,
                output_rate=0.0,
                inputs=[],
                status="no_recipe",
            )
            node_output_rate[node_id] = 0.0
            continue

        clock_speed = node.get("clock_speed", 1.0)
        craft_time  = recipe["craft_time"]          # seconds per cycle

        # Each recipe row in DB now has recipe['materials'] list attached by CRUD.
        items = recipe.get("materials", [])
        
        # Calculate items/min for each component
        # Formula: items_per_min = (amount / craft_time) * 60 * clock_speed
        input_list = []
        node_output_rate[node_id] = 0.0

        for item in items:
            rate = (item["amount"] / craft_time) * 60.0 * clock_speed
            if item["is_input"]:
                input_list.append({"material": item["material_name"], "rate": rate})
            else:
                # For now we assume one primary output for flow splitting
                # But we sum them if there are multiple (e.g. byproducts)
                node_output_rate[node_id] += rate

        result.nodes[node_id] = NodeResult(
            node_id=node_id,
            machine_name=machine_name,
            recipe_name=recipe["name"],
            output_rate=round(node_output_rate[node_id], 4),
            inputs=input_list,
            status="ok",
        )

    # --- Compute per-connection flow and status ---
    # Count outgoing connections per source node to split flow
    out_counts = {nid: len(adj) for nid, adj in graph["adjacency"].items()}

    for conn_id, conn in graph["connections"].items():
        src_id = conn["source_node_id"]
        tgt_id = conn["target_node_id"]

        # Split source production among all outgoing connections
        total_src_rate = node_output_rate.get(src_id, 0.0)
        num_conns      = out_counts.get(src_id, 1)
        src_rate       = total_src_rate / num_conns if num_conns > 0 else 0.0

        tgt_node_r  = result.nodes.get(tgt_id)
        # Total demand is the sum of inputs required by target
        demand = tgt_node_r.total_input_rate if tgt_node_r else 0.0

        mat = material_map.get(conn["material_id"]) if conn.get("material_id") else None
        mat_name = mat["name"] if mat else None

        if src_rate < demand - 0.001:
            status = "deficit"
        elif src_rate > demand + 0.001:
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
