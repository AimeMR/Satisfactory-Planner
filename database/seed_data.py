"""
database/seed_data.py
Seeds baseline Satisfactory game data (materials, machines, recipes).
Only inserts data if the tables are empty to avoid duplicates.
"""

from __future__ import annotations
from .crud import (
    add_material, add_machine, add_recipe,
    get_all_materials, get_all_machines,
)


def seed_db() -> None:
    """Seed all baseline game data. Safe to call multiple times."""
    if not get_all_materials():
        _seed_materials()
        _seed_machines()
        _seed_recipes()
        _seed_mining_recipes()
        print("[DB] Seed data inserted successfully.")
    else:
        print("[DB] Seed data already present, skipping.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_materials() -> None:
    """Insert all base materials."""
    items = [
        # Solids
        ("Iron Ore",       "solid"),
        ("Iron Ingot",     "solid"),
        ("Iron Plate",     "solid"),
        ("Iron Rod",       "solid"),
        ("Copper Ore",     "solid"),
        ("Copper Ingot",   "solid"),
        ("Wire",           "solid"),
        ("Cable",          "solid"),
        ("Concrete",       "solid"),
        ("Limestone",      "solid"),
        ("Coal",           "solid"),
        ("Steel Ingot",    "solid"),
        ("Steel Beam",     "solid"),
        ("Steel Pipe",     "solid"),
        ("Screw",          "solid"),
        ("Reinforced Iron Plate", "solid"),
        ("Rotor",          "solid"),
        ("Modular Frame",  "solid"),
        ("Plastic",        "solid"),
        ("Rubber",         "solid"),
        ("Silica",         "solid"),
        ("Quartz Crystal", "solid"),
        ("Raw Quartz",     "solid"),
        ("Caterium Ore",   "solid"),
        ("Caterium Ingot", "solid"),
        ("Quickwire",      "solid"),
        # Liquids / gases
        ("Water",          "liquid"),
        ("Crude Oil",      "liquid"),
        ("Heavy Oil Residue", "liquid"),
        ("Nitrogen Gas",   "gas"),
    ]
    for name, type_ in items:
        add_material(name, type_)


def _seed_machines() -> None:
    """Insert all base machine types."""
    machines = [
        # (name,               base_power, inputs, outputs)
        ("Miner Mk.1",         5.0,   0, 1),
        ("Miner Mk.2",        12.0,   0, 1),
        ("Miner Mk.3",        30.0,   0, 1),
        ("Water Extractor",   20.0,   0, 1),
        ("Oil Extractor",     40.0,   0, 1),
        ("Smelter",           12.0,   1, 1),
        ("Foundry",           16.0,   2, 1),
        ("Constructor",        4.0,   1, 1),
        ("Assembler",         15.0,   2, 1),
        ("Manufacturer",      55.0,   4, 1),
        ("Refinery",          30.0,   2, 2),
        ("Packager",          10.0,   2, 2),
    ]
    for name, power, inputs, outputs in machines:
        add_machine(name, power, inputs, outputs)


def _seed_recipes() -> None:
    """Insert base recipes with multiple inputs/outputs support."""
    from .db import get_connection
    conn = get_connection()

    def mat(name: str) -> int:
        row = conn.execute("SELECT id FROM Materials WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def mach(name: str) -> int:
        row = conn.execute("SELECT id FROM Machines WHERE name = ?", (name,)).fetchone()
        return row["id"]

    # Simple 1-to-1 recipes
    simple = [
        # (name, mach, in_name, in_qty, out_name, out_qty, time)
        ("Smelt Iron",     "Smelter",     "Iron Ore",     1, "Iron Ingot",     1, 2.0),
        ("Smelt Copper",   "Smelter",     "Copper Ore",   1, "Copper Ingot",   1, 2.0),
        ("Iron Plate",     "Constructor", "Iron Ingot",   3, "Iron Plate",     2, 6.0),
        ("Iron Rod",       "Constructor", "Iron Ingot",   1, "Iron Rod",       1, 4.0),
        ("Wire",           "Constructor", "Copper Ingot", 1, "Wire",           2, 4.0),
        ("Screw",          "Constructor", "Iron Rod",     1, "Screw",          4, 6.0),
    ]

    for name, mname, in_name, in_qty, out_name, out_qty, time in simple:
        ingredients = [
            {"material_id": mat(in_name),  "amount": in_qty,  "is_input": 1},
            {"material_id": mat(out_name), "amount": out_qty, "is_input": 0},
        ]
        add_recipe(name, mach(mname), ingredients, time)

    # Assembler 2-to-1 recipes
    assembler = [
        # name, in1, q1, in2, q2, out, qout, time
        ("Reinforced Iron Plate", "Iron Plate", 6, "Screw", 12, "Reinforced Iron Plate", 1, 12.0),
        ("Rotor",                 "Iron Rod",   5, "Screw", 25, "Rotor",                 1, 15.0),
        ("Modular Frame",         "Reinforced Iron Plate", 3, "Iron Rod", 12, "Modular Frame", 2, 60.0),
    ]
    for name, i1, q1, i2, q2, out, qout, time in assembler:
        ingredients = [
            {"material_id": mat(i1),  "amount": q1,   "is_input": 1},
            {"material_id": mat(i2),  "amount": q2,   "is_input": 1},
            {"material_id": mat(out), "amount": qout, "is_input": 0},
        ]
        add_recipe(name, mach("Assembler"), ingredients, time)


def _seed_mining_recipes() -> None:
    from .db import get_connection
    conn = get_connection()

    def mat(name: str) -> int:
        row = conn.execute("SELECT id FROM Materials WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def mach(name: str) -> int:
        row = conn.execute("SELECT id FROM Machines WHERE name = ?", (name,)).fetchone()
        return row["id"]

    ores = ["Iron Ore", "Copper Ore", "Limestone", "Coal", "Raw Quartz", "Caterium Ore"]
    miners = [("Miner Mk.1", 1), ("Miner Mk.2", 2), ("Miner Mk.3", 4)]

    for ore in ores:
        oid = mat(ore)
        for mname, qty in miners:
            ing = [{"material_id": oid, "amount": qty, "is_input": 0}]
            add_recipe(f"Mine {ore} ({mname})", mach(mname), ing, 1.0)

    # Water Extractor
    add_recipe("Extract Water", mach("Water Extractor"), 
               [{"material_id": mat("Water"), "amount": 2, "is_input": 0}], 1.0)

