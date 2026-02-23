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

    try:
        cursor.execute("SELECT * FROM Settings LIMIT 1")
    except sqlite3.OperationalError:
        # Just create the table if it's missing, no need to wipe entire DB
        # unless it's a major breaking change.
        cursor.execute("CREATE TABLE IF NOT EXISTS Settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()

    try:
        cursor.execute("SELECT category FROM Machines LIMIT 1")
        wipe_needed = False
    except sqlite3.OperationalError:
        print("[DB] Machine category schema missing. Wiping database...")
        wipe_needed = True

    if wipe_needed:
        global _connection
        if _connection:
            _connection.close()
            _connection = None
        
        # Give Windows a moment to release the file lock
        import time
        time.sleep(0.5)
        
        try:
            if os.path.exists(_DB_PATH):
                os.remove(_DB_PATH)
            print("[DB] Database wiped successfully.")
        except PermissionError:
            print("[DB] ERROR: Could not wipe database (file locked). Please close any other instances.")
            # We continue anyway and let it fail on CREATE TABLE if it really didn't wipe
        
        # Re-initialize connection
        conn = get_connection()
        cursor = conn.cursor()

    cursor.executescript("""
    -- All raw items and fluids in the game
    CREATE TABLE IF NOT EXISTS Materials (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name    TEXT    NOT NULL UNIQUE,
        type    TEXT    NOT NULL CHECK(type IN ('solid', 'liquid', 'gas'))
    );

    -- User preferences (Line style, sidebar visibility, etc.)
    CREATE TABLE IF NOT EXISTS Settings (
        key    TEXT PRIMARY KEY,
        value  TEXT
    );

    -- Base machine blueprints (Smelter, Constructor, etc.)
    CREATE TABLE IF NOT EXISTS Machines (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT    NOT NULL UNIQUE,
        category         TEXT    NOT NULL DEFAULT 'Other',
        base_power       REAL    NOT NULL DEFAULT 0,
        inputs_allowed   INTEGER NOT NULL DEFAULT 1,
        outputs_allowed  INTEGER NOT NULL DEFAULT 1
    );

    -- Base Recipe headers (Metadata only)
    CREATE TABLE IF NOT EXISTS Recipes (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT    NOT NULL,
        machine_id         INTEGER NOT NULL REFERENCES Machines(id),
        craft_time         REAL    NOT NULL DEFAULT 2.0
    );

    -- Multiple inputs/outputs per recipe
    CREATE TABLE IF NOT EXISTS Recipe_Materials (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe_id          INTEGER NOT NULL REFERENCES Recipes(id) ON DELETE CASCADE,
        material_id        INTEGER NOT NULL REFERENCES Materials(id),
        amount             REAL    NOT NULL,
        is_input           INTEGER NOT NULL DEFAULT 1  -- 1=input, 0=output
    );

    -- User-placed machine instances on the canvas
    CREATE TABLE IF NOT EXISTS Placed_Nodes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id    INTEGER NOT NULL REFERENCES Machines(id),
        recipe_id     INTEGER          REFERENCES Recipes(id),
        pos_x         REAL    NOT NULL DEFAULT 0,
        pos_y         REAL    NOT NULL DEFAULT 0,
        clock_speed   REAL    NOT NULL DEFAULT 1.0
    );

    -- Belt/pipe connections between nodes
    CREATE TABLE IF NOT EXISTS Connections (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        source_node_id   INTEGER NOT NULL REFERENCES Placed_Nodes(id) ON DELETE CASCADE,
        target_node_id   INTEGER NOT NULL REFERENCES Placed_Nodes(id) ON DELETE CASCADE,
        source_port_idx  INTEGER NOT NULL DEFAULT 0,
        target_port_idx  INTEGER NOT NULL DEFAULT 0,
        material_id      INTEGER          REFERENCES Materials(id),
        current_velocity REAL    NOT NULL DEFAULT 0
    );
    """)

    conn.commit()
    print("[DB] Tables initialized (Multi-Input Schema).")

