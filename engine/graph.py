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
    output_rate: float          # items/min produced
    input_rate_required: float  # items/min consumed
    status: str                 # "ok" | "no_recipe" | "disconnected"


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
                input_rate_required=0.0,
                status="no_recipe",
            )
            node_output_rate[node_id] = 0.0
            continue

        clock_speed = node.get("clock_speed", 1.0)
        craft_time  = recipe["craft_time"]          # seconds per cycle

        # items/min = (output_qty / craft_time) * 60 * clock_speed
        output_rate = (recipe["output_qty"] / craft_time) * 60.0 * clock_speed

        # Mining/extraction recipes have no belt input (input_qty == 0 or None)
        raw_input_qty = recipe.get("input_qty") or 0
        if raw_input_qty > 0 and recipe.get("input_material_id"):
            input_rate = (raw_input_qty / craft_time) * 60.0 * clock_speed
        else:
            input_rate = 0.0   # miners are pure producers — no input required

        node_output_rate[node_id] = output_rate
        recipe_name = recipe["name"]

        result.nodes[node_id] = NodeResult(
            node_id=node_id,
            machine_name=machine_name,
            recipe_name=recipe_name,
            output_rate=round(output_rate, 4),
            input_rate_required=round(input_rate, 4),
            status="ok",
        )

    # --- Compute per-connection flow and status ---
    for conn_id, conn in graph["connections"].items():
        src_id = conn["source_node_id"]
        tgt_id = conn["target_node_id"]

        src_rate    = node_output_rate.get(src_id, 0.0)
        tgt_node_r  = result.nodes.get(tgt_id)
        demand      = tgt_node_r.input_rate_required if tgt_node_r else 0.0

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
            capacity=round(src_rate, 4),
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
            print(f"       Consumes: {nr.input_rate_required} items/min")
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
