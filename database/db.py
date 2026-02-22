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
    """Create all tables if they do not exist yet, then run migrations."""
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

    -- Production recipes (each row = one input -> one output mapping)
    -- input_material_id is NULL for miners/extractors (no belt input needed)
    CREATE TABLE IF NOT EXISTS Recipes (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT    NOT NULL,
        machine_id         INTEGER NOT NULL REFERENCES Machines(id),
        input_material_id  INTEGER          REFERENCES Materials(id),
        input_qty          REAL    NOT NULL DEFAULT 0,
        output_material_id INTEGER NOT NULL REFERENCES Materials(id),
        output_qty         REAL    NOT NULL,
        craft_time         REAL    NOT NULL DEFAULT 2.0
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
    _migrate_recipes_nullable(conn)
    print("[DB] Tables created (or already exist).")


def _migrate_recipes_nullable(conn: "sqlite3.Connection") -> None:
    """
    If the Recipes table still has a NOT NULL constraint on input_material_id
    (old schema), rename-and-recreate it to allow NULL (for miners/extractors).
    """
    cols = conn.execute("PRAGMA table_info(Recipes)").fetchall()
    needs_migration = any(
        col["name"] == "input_material_id" and col["notnull"]
        for col in cols
    )
    if not needs_migration:
        return

    print("[DB] Migrating schema to allow nullable inputs and fix foreign keys...")
    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        -- 1. Rename old tables
        ALTER TABLE Connections RENAME TO _Connections_old;
        ALTER TABLE Placed_Nodes RENAME TO _Placed_Nodes_old;
        ALTER TABLE Recipes RENAME TO _Recipes_old;

        -- 2. Create new tables with correct schema
        CREATE TABLE Recipes (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            name               TEXT    NOT NULL,
            machine_id         INTEGER NOT NULL REFERENCES Machines(id),
            input_material_id  INTEGER          REFERENCES Materials(id),
            input_qty          REAL    NOT NULL DEFAULT 0.0,
            output_material_id INTEGER NOT NULL REFERENCES Materials(id),
            output_qty         REAL    NOT NULL,
            craft_time         REAL    NOT NULL DEFAULT 2.0
        );

        CREATE TABLE Placed_Nodes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id    INTEGER NOT NULL REFERENCES Machines(id),
            recipe_id     INTEGER          REFERENCES Recipes(id),
            pos_x         REAL    NOT NULL DEFAULT 0,
            pos_y         REAL    NOT NULL DEFAULT 0,
            clock_speed   REAL    NOT NULL DEFAULT 1.0
        );

        CREATE TABLE Connections (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            source_node_id   INTEGER NOT NULL REFERENCES Placed_Nodes(id) ON DELETE CASCADE,
            target_node_id   INTEGER NOT NULL REFERENCES Placed_Nodes(id) ON DELETE CASCADE,
            material_id      INTEGER          REFERENCES Materials(id),
            current_velocity REAL    NOT NULL DEFAULT 0
        );

        -- 3. Restore data
        INSERT INTO Recipes (id, name, machine_id, input_material_id, input_qty, output_material_id, output_qty, craft_time)
            SELECT id, name, machine_id, input_material_id, input_qty, output_material_id, output_qty, craft_time
            FROM _Recipes_old;

        INSERT INTO Placed_Nodes (id, machine_id, recipe_id, pos_x, pos_y, clock_speed)
            SELECT id, machine_id, recipe_id, pos_x, pos_y, clock_speed
            FROM _Placed_Nodes_old;

        INSERT INTO Connections (id, source_node_id, target_node_id, material_id, current_velocity)
            SELECT id, source_node_id, target_node_id, material_id, current_velocity
            FROM _Connections_old;

        -- 4. Clean up
        DROP TABLE _Connections_old;
        DROP TABLE _Placed_Nodes_old;
        DROP TABLE _Recipes_old;

        PRAGMA foreign_keys = ON;
    """)
    conn.commit()
    print("[DB] Migration complete.")
