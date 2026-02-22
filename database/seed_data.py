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
    if get_all_materials():
        print("[DB] Seed data already present, skipping.")
        return

    _seed_materials()
    _seed_machines()
    _seed_recipes()
    print("[DB] Seed data inserted successfully.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_materials() -> dict[str, int]:
    """Insert all base materials and return a name→id mapping."""
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
    """
    Insert base recipes.
    We look up material/machine IDs by re-querying (seed runs once, so it's fine).
    """
    from .db import get_connection
    conn = get_connection()

    def mat(name: str) -> int:
        row = conn.execute("SELECT id FROM Materials WHERE name = ?", (name,)).fetchone()
        if not row:
            raise ValueError(f"Material not found: {name}")
        return row["id"]  # type: ignore[index]

    def mach(name: str) -> int:
        row = conn.execute("SELECT id FROM Machines WHERE name = ?", (name,)).fetchone()
        if not row:
            raise ValueError(f"Machine not found: {name}")
        return row["id"]  # type: ignore[index]

    # Quantities are PER-CYCLE (not per-minute).
    # Engine formula: items_per_min = (qty / craft_time_s) * 60
    #
    # Quick reference for expected rates:
    #   Smelt Iron:   1 ore in / 1 ingot out / 2s  → 30 ore/min consumed, 30 ingot/min produced
    #   Iron Plate:   3 ingot in / 2 plate out / 6s → 30 ingot/min consumed, 20 plate/min produced
    #   Iron Rod:     1 ingot in / 1 rod out / 4s   → 15 each/min
    #   Wire:         1 cu-ingot in / 2 wire out / 4s → 15 in, 30 out /min
    #   Cable:        4 wire in / 2 cable out / 4s  → 60 in, 30 out /min
    #   Concrete:     3 limestone in / 1 concrete out / 4s → 45 in, 15 out /min
    #   Steel Beam:   4 steel in / 1 beam out / 4s  → 60 in, 15 out /min
    #   Steel Pipe:   3 steel in / 2 pipe out / 6s  → 30 in, 20 out /min
    #   Screw:        1 rod in / 4 screw out / 6s   → 10 in, 40 out /min
    recipes = [
        # (name, machine, input_mat, in_qty, output_mat, out_qty, craft_time_s)
        # --- Smelter ---
        ("Smelt Iron",            "Smelter",     "Iron Ore",              1, "Iron Ingot",             1,  2.0),
        ("Smelt Copper",          "Smelter",     "Copper Ore",            1, "Copper Ingot",           1,  2.0),
        ("Smelt Caterium",        "Smelter",     "Caterium Ore",          3, "Caterium Ingot",         1,  4.0),
        # --- Foundry ---
        ("Smelt Steel",           "Foundry",     "Iron Ore",              3, "Steel Ingot",            3,  4.0),
        # --- Constructor ---
        ("Iron Plate",            "Constructor", "Iron Ingot",            3, "Iron Plate",             2,  6.0),
        ("Iron Rod",              "Constructor", "Iron Ingot",            1, "Iron Rod",               1,  4.0),
        ("Wire",                  "Constructor", "Copper Ingot",          1, "Wire",                   2,  4.0),
        ("Cable",                 "Constructor", "Wire",                  4, "Cable",                  2,  4.0),
        ("Concrete",              "Constructor", "Limestone",             3, "Concrete",               1,  4.0),
        ("Steel Beam",            "Constructor", "Steel Ingot",           4, "Steel Beam",             1,  4.0),
        ("Steel Pipe",            "Constructor", "Steel Ingot",           3, "Steel Pipe",             2,  6.0),
        ("Screw",                 "Constructor", "Iron Rod",              1, "Screw",                  4,  6.0),
        ("Quickwire",             "Constructor", "Caterium Ingot",        1, "Quickwire",              5,  5.0),
        ("Quartz Crystal",        "Constructor", "Raw Quartz",            5, "Quartz Crystal",         3,  8.0),
        ("Silica",                "Constructor", "Raw Quartz",            4, "Silica",                 7, 11.0),
        # --- Assembler ---
        ("Reinforced Iron Plate", "Assembler",   "Iron Plate",            6, "Reinforced Iron Plate",  1, 12.0),
        ("Rotor",                 "Assembler",   "Iron Rod",              5, "Rotor",                  1, 15.0),
        ("Modular Frame",         "Assembler",   "Reinforced Iron Plate", 3, "Modular Frame",          2, 60.0),
    ]

    for name, machine, in_mat, in_qty, out_mat, out_qty, craft_time in recipes:
        add_recipe(
            name=name,
            machine_id=mach(machine),
            input_material_id=mat(in_mat),
            input_qty=in_qty,
            output_material_id=mat(out_mat),
            output_qty=out_qty,
            craft_time=craft_time,
        )
