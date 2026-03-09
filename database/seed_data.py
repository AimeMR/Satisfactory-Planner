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
    from database.crud import get_setting, set_setting
    current_version = get_setting("seed_version", "0")
    SEED_VERSION = "3"  # Increment when seed data changes
    
    if current_version != SEED_VERSION:
        _seed_materials()
        _seed_machines()
        _seed_recipes()
        _seed_mining_recipes()
        set_setting("seed_version", SEED_VERSION)
        print("[DB] Seed data inserted/updated successfully.")
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
        ("Aluminum Ore",   "solid"),
        ("Aluminum Ingot", "solid"),
        ("Alclad Aluminum Sheet", "solid"),
        ("Aluminum Casing", "solid"),
        ("Bauxite",        "solid"),
        ("Copper Powder",   "solid"),
        ("Heat Sink",       "solid"),
        ("Pressure Conversion Cube", "solid"),
        ("Uranium",        "solid"),
        ("Uranium Waste",  "solid"),
        ("Sulfur",         "solid"),
        ("Compact Coal",   "solid"),
        ("Battery",        "solid"),
        ("Supercomputer",  "solid"),
        ("Computer",       "solid"),
        ("Circuit Board",  "solid"),
        ("High-Speed Connector", "solid"),
        ("AI Limiter",     "solid"),
        ("Heavy Modular Frame", "solid"),
        ("Fused Modular Frame", "solid"),
        ("Space Elevator Part", "solid"),
        ("Copper Sheet",    "solid"),
        ("Stator",          "solid"),
        ("Motor",           "solid"),
        ("Cooling System",  "solid"),
        ("Turbo Motor",     "solid"),
        ("Adaptive Control Unit", "solid"),
        ("Modular Engine",  "solid"),
        ("Smart Plating",   "solid"),
        ("Versatile Framework", "solid"),
        ("Automated Wiring", "solid"),
        ("Crystal Oscillator", "solid"),
        ("Radio Control Unit", "solid"),
        ("Nuclear Pasta",   "solid"),
        ("Assembly Director System", "solid"),
        ("Magnetic Field Generator", "solid"),
        ("Thermal Propulsion Rocket", "solid"),
        ("Biomass",         "solid"),
        ("Electromagnetic Control Rod", "solid"),
        ("Non-Fissile Uranium", "solid"),
        ("Plutonium Pellet",  "solid"),
        ("Encased Plutonium Cell", "solid"),
        ("Plutonium Fuel Rod", "solid"),
        ("Uranium Fuel Rod",   "solid"),
        ("Encased Uranium Cell", "solid"),
        ("Aluminum Scrap",  "solid"),
        # Liquids / gases
        ("Water",          "liquid"),
        ("Crude Oil",      "liquid"),
        ("Heavy Oil Residue", "liquid"),
        ("Fuel",           "liquid"),
        ("Turbo Fuel",     "liquid"),
        ("Nitrogen Gas",   "gas"),
        ("Alumina Solution", "liquid"),
        ("Sulfuric Acid",  "liquid"),
        ("Nitric Acid",    "liquid"),
    ]
    for name, type_ in items:
        add_material(name, type_)


def _seed_machines() -> None:
    """Insert all base machine types with categories."""
    machines = [
        # (name,               category,     power, inputs, outputs)
        ("Miner Mk.1",         "Extraction",  5.0,   0, 1),
        ("Miner Mk.2",         "Extraction", 12.0,   0, 1),
        ("Miner Mk.3",         "Extraction", 30.0,   0, 1),
        ("Water Extractor",    "Extraction", 20.0,   0, 1),
        ("Oil Extractor",      "Extraction", 40.0,   0, 1),
        ("Resource Well Pressurizer", "Extraction", 150.0, 0, 1),
        ("Smelter",            "Production", 12.0,   1, 1),
        ("Foundry",            "Production", 16.0,   2, 1),
        ("Constructor",        "Production",  4.0,   1, 1),
        ("Assembler",          "Production", 15.0,   2, 1),
        ("Manufacturer",       "Production", 55.0,   4, 1),
        ("Refinery",           "Production", 30.0,   2, 2),
        ("Packager",           "Production", 10.0,   2, 2),
        ("Blender",            "Production", 75.0,   4, 2),
        ("Particle Accelerator", "Production", 500.0, 2, 1),
        ("Fuel Generator",     "Power",      0.0,    1, 0),
        ("Nuclear Power Plant", "Power",      0.0,    2, 1),
        ("Conveyor Splitter",  "Logistics",   0.0,   1, 3),
        ("Conveyor Merger",    "Logistics",   0.0,   3, 1),
    ]
    for name, cat, power, inputs, outputs in machines:
        add_machine(name, cat, power, inputs, outputs)


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
        ("Cable",          "Constructor", "Wire",          2, "Cable",          1, 2.0), # Actually Constructor
        ("Biomass",        "Constructor", "Limestone",    1, "Biomass",        1, 1.0), # Generic placeholder for biomass
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
        ("Circuit Board",         "Copper Ingot", 2, "Plastic", 2, "Circuit Board", 1, 8.0),
        ("Stator",                "Steel Pipe", 3, "Wire", 8, "Stator", 1, 12.0),
        ("Motor",                 "Rotor", 2, "Stator", 2, "Motor", 1, 12.0),
        ("AI Limiter",            "Copper Sheet", 5, "Quickwire", 20, "AI Limiter", 1, 12.0),
        # Space Elevator
        ("Smart Plating",         "Reinforced Iron Plate", 1, "Rotor", 1, "Smart Plating", 1, 30.0),
        ("Versatile Framework",   "Modular Frame", 1, "Steel Beam", 12, "Versatile Framework", 2, 24.0),
        ("Automated Wiring",      "Stator", 1, "Cable", 20, "Automated Wiring", 1, 30.0),
    ]
    for name, i1, q1, i2, q2, out, qout, time in assembler:
        ingredients = [
            {"material_id": mat(i1),  "amount": q1,   "is_input": 1},
            {"material_id": mat(i2),  "amount": q2,   "is_input": 1},
            {"material_id": mat(out), "amount": qout, "is_input": 0},
        ]
        add_recipe(name, mach("Assembler"), ingredients, time)

    # Steel & Advanced Production
    others = [
        # Smelter
        ("Steel Ingot", "Foundry", [("Iron Ore", 3), ("Coal", 3)], [("Steel Ingot", 3)], 4.0),
        ("Solid Steel", "Foundry", [("Iron Ingot", 2), ("Coal", 2)], [("Steel Ingot", 3)], 3.0),
        
        # Constructor
        ("Steel Beam", "Constructor", [("Steel Ingot", 4)], [("Steel Beam", 1)], 4.0),
        ("Steel Pipe", "Constructor", [("Steel Ingot", 3)], [("Steel Pipe", 2)], 6.0),
        ("Concrete", "Constructor", [("Limestone", 3)], [("Concrete", 1)], 4.0),
        ("Copper Sheet", "Constructor", [("Copper Ingot", 2)], [("Copper Sheet", 1)], 6.0),
        ("Quickwire", "Constructor", [("Caterium Ingot", 1)], [("Quickwire", 5)], 5.0),
        ("Quartz Crystal", "Constructor", [("Raw Quartz", 3)], [("Quartz Crystal", 2)], 8.0),
        ("Silica", "Constructor", [("Raw Quartz", 3)], [("Silica", 5)], 8.0),
        ("Aluminum Casing", "Constructor", [("Aluminum Ingot", 3)], [("Aluminum Casing", 2)], 3.0),
        
        # Refinery (Supports liquid/solid)
        ("Plastic", "Refinery", [("Crude Oil", 3)], [("Plastic", 2), ("Heavy Oil Residue", 1)], 6.0),
        ("Rubber", "Refinery", [("Crude Oil", 3)], [("Rubber", 2), ("Heavy Oil Residue", 1)], 6.0),
        ("Fuel", "Refinery", [("Crude Oil", 6)], [("Fuel", 4), ("Heavy Oil Residue", 3)], 6.0),
        ("Alumina Solution", "Refinery", [("Bauxite", 12), ("Water", 18)], [("Alumina Solution", 12), ("Silica", 5)], 6.0),
        ("Aluminum Scrap", "Refinery", [("Alumina Solution", 4), ("Coal", 2)], [("Aluminum Scrap", 6), ("Water", 2)], 1.0),
        ("Aluminum Ingot", "Smelter", [("Aluminum Scrap", 6), ("Silica", 5)], [("Aluminum Ingot", 4)], 4.0),
        
        # Manufacturer
        ("Computer", "Manufacturer", [("Circuit Board", 10), ("Cable", 9), ("Plastic", 18), ("Screw", 52)], [("Computer", 1)], 24.0),
        ("Heavy Modular Frame", "Manufacturer", [("Modular Frame", 5), ("Steel Pipe", 15), ("Steel Beam", 5), ("Screw", 100)], [("Heavy Modular Frame", 1)], 30.0),
        ("Supercomputer", "Manufacturer", [("Computer", 2), ("AI Limiter", 2), ("High-Speed Connector", 3), ("Plastic", 28)], [("Supercomputer", 1)], 32.0),
        ("Crystal Oscillator", "Manufacturer", [("Quartz Crystal", 18), ("Cable", 14), ("Reinforced Iron Plate", 2)], [("Crystal Oscillator", 1)], 120.0),
        ("Radio Control Unit", "Manufacturer", [("Aluminum Casing", 32), ("Crystal Oscillator", 1), ("Computer", 1)], [("Radio Control Unit", 1)], 48.0),
        
        # Blender
        ("Battery", "Blender", [("Sulfuric Acid", 50), ("Alumina Solution", 40), ("Aluminum Casing", 20)], [("Battery", 20)], 6.0),
        ("Cooling System", "Blender", [("Heat Sink", 2), ("Rubber", 2), ("Water", 5)], [("Cooling System", 1)], 10.0), # Simplified components
        ("Turbo Motor", "Blender", [("Cooling System", 4), ("Radio Control Unit", 2), ("Motor", 4)], [("Turbo Motor", 1)], 32.0),
        
        # Space Elevator Project Parts (Manufacturer / Assembler)
        ("Modular Engine", "Manufacturer", [("Motor", 2), ("Rubber", 15), ("Smart Plating", 2)], [("Modular Engine", 1)], 60.0),
        ("Adaptive Control Unit", "Manufacturer", [("Automated Wiring", 15), ("Circuit Board", 10), ("Heavy Modular Frame", 1)], [("Adaptive Control Unit", 1)], 120.0),
        
        # Particle Accelerator
        ("Nuclear Pasta", "Particle Accelerator", [("Copper Powder", 200), ("Pressure Conversion Cube", 1)], [("Nuclear Pasta", 1)], 120.0),

        # Phase 4 Space Elevator parts
        ("Assembly Director System", "Manufacturer", [("Adaptive Control Unit", 2), ("Supercomputer", 1)], [("Assembly Director System", 1)], 80.0),
        ("Magnetic Field Generator", "Manufacturer", [("Versatile Framework", 5), ("Electromagnetic Control Rod", 1)], [("Magnetic Field Generator", 2)], 120.0),
        ("Thermal Propulsion Rocket", "Manufacturer", [("Modular Engine", 5), ("Turbo Motor", 2), ("Cooling System", 3), ("Fused Modular Frame", 1)], [("Thermal Propulsion Rocket", 2)], 120.0),
        
        # Tier 8 & Nuclear Advanced
        ("Fused Modular Frame", "Blender", [("Heavy Modular Frame", 1), ("Aluminum Casing", 50), ("Nitrogen Gas", 25)], [("Fused Modular Frame", 1)], 20.0),
        ("Pressure Conversion Cube", "Assembler", [("Fused Modular Frame", 1), ("Radio Control Unit", 2)], [("Pressure Conversion Cube", 1)], 60.0),
        ("Electromagnetic Control Rod", "Assembler", [("Stator", 3), ("AI Limiter", 2)], [("Electromagnetic Control Rod", 1)], 30.0),
        ("Encased Uranium Cell", "Blender", [("Uranium", 10), ("Concrete", 3), ("Sulfuric Acid", 8)], [("Encased Uranium Cell", 5)], 12.0),
        ("Uranium Fuel Rod", "Manufacturer", [("Encased Uranium Cell", 20), ("Electromagnetic Control Rod", 1), ("Crystal Oscillator", 3)], [("Uranium Fuel Rod", 1)], 120.0),
        ("Non-Fissile Uranium", "Blender", [("Uranium Waste", 15), ("Silica", 10), ("Nitric Acid", 6), ("Sulfuric Acid", 6)], [("Non-Fissile Uranium", 20), ("Water", 6)], 12.0),
        ("Plutonium Pellet", "Particle Accelerator", [("Non-Fissile Uranium", 100), ("Uranium Waste", 25)], [("Plutonium Pellet", 30)], 60.0),
        ("Encased Plutonium Cell", "Assembler", [("Plutonium Pellet", 2), ("Concrete", 4)], [("Encased Plutonium Cell", 1)], 12.0),
        ("Plutonium Fuel Rod", "Manufacturer", [("Encased Plutonium Cell", 30), ("Steel Beam", 18), ("Electromagnetic Control Rod", 6), ("Heat Sink", 10)], [("Plutonium Fuel Rod", 1)], 120.0),
    ]

    for rname, mname, inputs, outputs, time in others:
        ingredients = []
        for in_mat, in_qty in inputs:
            ingredients.append({"material_id": mat(in_mat), "amount": in_qty, "is_input": 1})
        for out_mat, out_qty in outputs:
            ingredients.append({"material_id": mat(out_mat), "amount": out_qty, "is_input": 0})
        add_recipe(rname, mach(mname), ingredients, time)


def _seed_mining_recipes() -> None:
    from .db import get_connection
    conn = get_connection()

    def mat(name: str) -> int:
        row = conn.execute("SELECT id FROM Materials WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def mach(name: str) -> int:
        row = conn.execute("SELECT id FROM Machines WHERE name = ?", (name,)).fetchone()
        return row["id"]

    ores = [
        "Iron Ore", "Copper Ore", "Limestone", "Coal", 
        "Raw Quartz", "Caterium Ore", "Bauxite", "Sulfur", "Uranium"
    ]
    miners = [("Miner Mk.1", 1), ("Miner Mk.2", 2), ("Miner Mk.3", 4)]

    for ore in ores:
        oid = mat(ore)
        for mname, qty in miners:
            ing = [{"material_id": oid, "amount": qty, "is_input": 0}]
            add_recipe(f"Mine {ore} ({mname})", mach(mname), ing, 1.0)

    # Extraction Machines (Fluids/Special)
    extradata = [
        ("Extract Water", "Water Extractor", [("Water", 2)]),
        ("Extract Crude Oil", "Oil Extractor", [("Crude Oil", 4)]),
        ("Extract Nitrogen Gas", "Resource Well Pressurizer", [("Nitrogen Gas", 10)]),
    ]
    
    for rname, mname, outputs in extradata:
        ing = []
        for out_mat, out_qty in outputs:
            ing.append({"material_id": mat(out_mat), "amount": out_qty, "is_input": 0})
        add_recipe(rname, mach(mname), ing, 1.0)

