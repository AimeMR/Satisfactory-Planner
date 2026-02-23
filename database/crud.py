"""
database/crud.py
CRUD operations for every table in satisfactory.db.
All functions accept/return plain Python dicts or lists of dicts.
"""

from __future__ import annotations
from .db import get_connection


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def get_all_materials() -> list[dict]:
    rows = get_connection().execute("SELECT * FROM Materials ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_material_by_id(material_id: int) -> dict | None:
    row = get_connection().execute(
        "SELECT * FROM Materials WHERE id = ?", (material_id,)
    ).fetchone()
    return dict(row) if row else None


def add_material(name: str, type_: str) -> int:
    """Insert a material and return its new id."""
    conn = get_connection()
    cur = conn.execute("INSERT OR IGNORE INTO Materials (name, type) VALUES (?, ?)", (name, type_))
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute("SELECT id FROM Materials WHERE name = ?", (name,)).fetchone()
    return row["id"]


# ---------------------------------------------------------------------------
# Machines
# ---------------------------------------------------------------------------

def get_all_machines() -> list[dict]:
    rows = get_connection().execute("SELECT * FROM Machines ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_machine_by_id(machine_id: int) -> dict | None:
    row = get_connection().execute(
        "SELECT * FROM Machines WHERE id = ?", (machine_id,)
    ).fetchone()
    return dict(row) if row else None


def add_machine(name: str, base_power: float,
                inputs_allowed: int, outputs_allowed: int) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT OR IGNORE INTO Machines (name, base_power, inputs_allowed, outputs_allowed) "
        "VALUES (?, ?, ?, ?)",
        (name, base_power, inputs_allowed, outputs_allowed),
    )
    conn.commit()
    if cur.lastrowid:
        return cur.lastrowid
    row = conn.execute("SELECT id FROM Machines WHERE name = ?", (name,)).fetchone()
    return row["id"]


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------

def _attach_materials_to_recipe(recipe_row: sqlite3.Row) -> dict:
    recipe = dict(recipe_row)
    rows = get_connection().execute("""
        SELECT rm.*, m.name as material_name
        FROM Recipe_Materials rm
        JOIN Materials m ON rm.material_id = m.id
        WHERE rm.recipe_id = ?
    """, (recipe["id"],)).fetchall()
    recipe["materials"] = [dict(r) for r in rows]
    return recipe


def get_all_recipes() -> list[dict]:
    rows = get_connection().execute("SELECT * FROM Recipes").fetchall()
    return [_attach_materials_to_recipe(r) for r in rows]


def get_recipes_for_machine(machine_id: int) -> list[dict]:
    rows = get_connection().execute(
        "SELECT * FROM Recipes WHERE machine_id = ?", (machine_id,)
    ).fetchall()
    return [_attach_materials_to_recipe(r) for r in rows]


def get_recipe_by_id(recipe_id: int) -> dict | None:
    row = get_connection().execute(
        "SELECT * FROM Recipes WHERE id = ?", (recipe_id,)
    ).fetchone()
    return _attach_materials_to_recipe(row) if row else None


def add_recipe(name: str, machine_id: int, ingredients: list[dict], craft_time: float = 2.0) -> int:
    """
    Insert a recipe and its materials.
    ingredients: List of {"material_id": int, "amount": float, "is_input": bool}
    """
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO Recipes (name, machine_id, craft_time) VALUES (?, ?, ?)",
        (name, machine_id, craft_time),
    )
    recipe_id = cur.lastrowid
    for ing in ingredients:
        conn.execute(
            "INSERT INTO Recipe_Materials (recipe_id, material_id, amount, is_input) "
            "VALUES (?, ?, ?, ?)",
            (recipe_id, ing["material_id"], ing["amount"], ing["is_input"]),
        )
    conn.commit()
    return recipe_id


# ---------------------------------------------------------------------------
# Placed Nodes
# ---------------------------------------------------------------------------

def get_all_placed_nodes() -> list[dict]:
    rows = get_connection().execute("SELECT * FROM Placed_Nodes").fetchall()
    return [dict(r) for r in rows]


def get_placed_node_by_id(node_id: int) -> dict | None:
    row = get_connection().execute(
        "SELECT * FROM Placed_Nodes WHERE id = ?", (node_id,)
    ).fetchone()
    return dict(row) if row else None


def add_placed_node(machine_id: int, recipe_id: int | None = None,
                    pos_x: float = 0.0, pos_y: float = 0.0,
                    clock_speed: float = 1.0) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO Placed_Nodes (machine_id, recipe_id, pos_x, pos_y, clock_speed) "
        "VALUES (?, ?, ?, ?, ?)",
        (machine_id, recipe_id, pos_x, pos_y, clock_speed),
    )
    conn.commit()
    return cur.lastrowid


def update_placed_node(node_id: int, **kwargs) -> None:
    """Update any subset of fields on a placed node.
    
    Allowed kwargs: recipe_id, pos_x, pos_y, clock_speed
    """
    allowed = {"recipe_id", "pos_x", "pos_y", "clock_speed"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [node_id]
    conn.execute(f"UPDATE Placed_Nodes SET {sets} WHERE id = ?", values)
    conn.commit()


def delete_placed_node(node_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM Placed_Nodes WHERE id = ?", (node_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def get_all_connections() -> list[dict]:
    rows = get_connection().execute("SELECT * FROM Connections").fetchall()
    return [dict(r) for r in rows]


def get_connections_for_node(node_id: int) -> list[dict]:
    """Return all connections where this node is source OR target."""
    rows = get_connection().execute(
        "SELECT * FROM Connections "
        "WHERE source_node_id = ? OR target_node_id = ?",
        (node_id, node_id),
    ).fetchall()
    return [dict(r) for r in rows]


def add_connection(source_node_id: int, target_node_id: int,
                   material_id: int | None = None,
                   current_velocity: float = 0.0) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO Connections "
        "(source_node_id, target_node_id, material_id, current_velocity) "
        "VALUES (?, ?, ?, ?)",
        (source_node_id, target_node_id, material_id, current_velocity),
    )
    conn.commit()
    return cur.lastrowid


def update_connection_velocity(connection_id: int, velocity: float) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE Connections SET current_velocity = ? WHERE id = ?",
        (velocity, connection_id),
    )
    conn.commit()


def delete_connection(connection_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM Connections WHERE id = ?", (connection_id,))
    conn.commit()
