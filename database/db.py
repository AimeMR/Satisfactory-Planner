"""
database/db.py
Manages the SQLite connection and table initialization.
"""

import sqlite3
import os

# The .db file lives at the project root
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "satisfactory.db")
_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """Return a singleton SQLite connection with foreign keys enabled."""
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(os.path.abspath(_DB_PATH))
        _connection.row_factory = sqlite3.Row          # access columns by name
        _connection.execute("PRAGMA foreign_keys = ON")
        _connection.commit()
    return _connection


def close_connection() -> None:
    """Close the active connection (call on app exit)."""
    global _connection
    if _connection:
        _connection.close()
        _connection = None


def initialize_db() -> None:
    """Create all tables if they do not exist yet."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    -- All raw items and fluids in the game
    CREATE TABLE IF NOT EXISTS Materials (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT    NOT NULL UNIQUE,
        type    TEXT    NOT NULL CHECK(type IN ('solid', 'liquid', 'gas'))
    );

    -- Base machine blueprints (Smelter, Constructor, etc.)
    CREATE TABLE IF NOT EXISTS Machines (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT    NOT NULL UNIQUE,
        base_power       REAL    NOT NULL DEFAULT 0,
        inputs_allowed   INTEGER NOT NULL DEFAULT 1,
        outputs_allowed  INTEGER NOT NULL DEFAULT 1
    );

    -- Production recipes (each row = one input → one output mapping)
    CREATE TABLE IF NOT EXISTS Recipes (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT    NOT NULL,
        machine_id         INTEGER NOT NULL REFERENCES Machines(id),
        input_material_id  INTEGER NOT NULL REFERENCES Materials(id),
        input_qty          REAL    NOT NULL,
        output_material_id INTEGER NOT NULL REFERENCES Materials(id),
        output_qty         REAL    NOT NULL,
        craft_time         REAL    NOT NULL DEFAULT 2.0  -- seconds per cycle
    );

    -- User-placed machine instances on the canvas
    CREATE TABLE IF NOT EXISTS Placed_Nodes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id    INTEGER NOT NULL REFERENCES Machines(id),
        recipe_id     INTEGER          REFERENCES Recipes(id),
        pos_x         REAL    NOT NULL DEFAULT 0,
        pos_y         REAL    NOT NULL DEFAULT 0,
        clock_speed   REAL    NOT NULL DEFAULT 1.0  -- 0.01 to 2.5 (overclock)
    );

    -- Belt/pipe connections between nodes
    CREATE TABLE IF NOT EXISTS Connections (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        source_node_id   INTEGER NOT NULL REFERENCES Placed_Nodes(id) ON DELETE CASCADE,
        target_node_id   INTEGER NOT NULL REFERENCES Placed_Nodes(id) ON DELETE CASCADE,
        material_id      INTEGER          REFERENCES Materials(id),
        current_velocity REAL    NOT NULL DEFAULT 0
    );
    """)

    conn.commit()
    print("[DB] Tables created (or already exist).")
