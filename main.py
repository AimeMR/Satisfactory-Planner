"""
main.py
CLI entry point for Phase 1 smoke-test.

Initializes the database, seeds game data, places two nodes,
connects them, runs the production engine, and prints results.
"""

import sys
import os

# Make sure local packages resolve correctly when run from any directory
sys.path.insert(0, os.path.dirname(__file__))

from database.db       import initialize_db, close_connection
from database.seed_data import seed_db
from database.crud     import (
    add_placed_node, add_connection,
    get_all_placed_nodes, get_all_connections,
    get_all_recipes, get_all_machines, get_all_materials,
    get_recipes_for_machine, get_machine_by_id,
)
from engine.graph import build_graph, calculate_production, print_results


def _find_machine_id(machines: list[dict], name: str) -> int:
    for m in machines:
        if m["name"] == name:
            return m["id"]
    raise ValueError(f"Machine '{name}' not found in DB.")


def _find_recipe_id(machine_id: int, recipe_name: str) -> int:
    for r in get_recipes_for_machine(machine_id):
        if r["name"] == recipe_name:
            return r["id"]
    raise ValueError(f"Recipe '{recipe_name}' not found for machine_id={machine_id}.")


def _find_material_id(materials: list[dict], name: str) -> int:
    for m in materials:
        if m["name"] == name:
            return m["id"]
    raise ValueError(f"Material '{name}' not found in DB.")


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Initialize DB & seed game data
    # ------------------------------------------------------------------
    initialize_db()
    seed_db()

    machines  = get_all_machines()
    materials = get_all_materials()

    # ------------------------------------------------------------------
    # 2. Place two nodes: Smelter → Constructor
    #    Smelter: Iron Ore → Iron Ingot (30/min)
    #    Constructor: Iron Ingot → Iron Plate (20/min)
    # ------------------------------------------------------------------
    smelter_id     = _find_machine_id(machines, "Smelter")
    constructor_id = _find_machine_id(machines, "Constructor")

    smelt_recipe_id  = _find_recipe_id(smelter_id,     "Smelt Iron")
    plate_recipe_id  = _find_recipe_id(constructor_id, "Iron Plate")

    node1_id = add_placed_node(
        machine_id=smelter_id,
        recipe_id=smelt_recipe_id,
        pos_x=0.0, pos_y=0.0,
        clock_speed=1.0,
    )
    node2_id = add_placed_node(
        machine_id=constructor_id,
        recipe_id=plate_recipe_id,
        pos_x=200.0, pos_y=0.0,
        clock_speed=1.0,
    )
    print(f"[LAYOUT] Placed Node {node1_id} (Smelter) and Node {node2_id} (Constructor).")

    # ------------------------------------------------------------------
    # 3. Connect the two nodes (Iron Ingot belt)
    # ------------------------------------------------------------------
    iron_ingot_id = _find_material_id(materials, "Iron Ingot")
    conn_id = add_connection(
        source_node_id=node1_id,
        target_node_id=node2_id,
        material_id=iron_ingot_id,
    )
    print(f"[LAYOUT] Created Connection {conn_id} (Iron Ingot belt).")

    # ------------------------------------------------------------------
    # 4. Run the production engine
    # ------------------------------------------------------------------
    placed_nodes = get_all_placed_nodes()
    connections  = get_all_connections()
    recipes      = get_all_recipes()

    graph  = build_graph(placed_nodes, connections)
    result = calculate_production(graph, recipes, machines, materials)

    # ------------------------------------------------------------------
    # 5. Print results
    # ------------------------------------------------------------------
    print_results(result)

    # ------------------------------------------------------------------
    # 6. Cleanup
    # ------------------------------------------------------------------
    close_connection()


if __name__ == "__main__":
    main()
