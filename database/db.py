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
        cursor.execute("SELECT project_id FROM Placed_Nodes LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] Missing project support. Migrating schema...")
        # 1. Create Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Projects (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL UNIQUE,
                last_modified  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 2. Add project_id to Placed_Nodes
        cursor.execute("ALTER TABLE Placed_Nodes ADD COLUMN project_id INTEGER REFERENCES Projects(id) ON DELETE CASCADE")
        
        # 3. Create a Default Project if none exists
        cursor.execute("INSERT OR IGNORE INTO Projects (id, name) VALUES (1, 'Default Project')")
        
        # 4. Migrate existing nodes
        cursor.execute("UPDATE Placed_Nodes SET project_id = 1 WHERE project_id IS NULL")
        conn.commit()

    # Settings table is safe with IF NOT EXISTS
    cursor.execute("CREATE TABLE IF NOT EXISTS Settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()

    # Groups and Grouping Migration
    try:
        cursor.execute("SELECT group_id FROM Placed_Nodes LIMIT 1")
    except sqlite3.OperationalError:
        print("[DB] Grouping schema missing. Adding Groups table and group_id...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Groups (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id   INTEGER NOT NULL REFERENCES Projects(id) ON DELETE CASCADE,
                name         TEXT    NOT NULL,
                pos_x        REAL    NOT NULL DEFAULT 0,
                pos_y        REAL    NOT NULL DEFAULT 0,
                is_collapsed INTEGER NOT NULL DEFAULT 0 -- 0=expanded, 1=collapsed
            )
        """)
        cursor.execute("ALTER TABLE Placed_Nodes ADD COLUMN group_id INTEGER REFERENCES Groups(id) ON DELETE SET NULL")
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

    -- Multiple projects
    CREATE TABLE IF NOT EXISTS Projects (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT    NOT NULL UNIQUE,
        last_modified  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- User preferences (Line style, sidebar visibility, etc.)
    CREATE TABLE IF NOT EXISTS Settings (
        key    TEXT PRIMARY KEY,
        value  TEXT
    );

    -- Logical groups of machines
    CREATE TABLE IF NOT EXISTS Groups (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id   INTEGER NOT NULL REFERENCES Projects(id) ON DELETE CASCADE,
        name         TEXT    NOT NULL,
        pos_x        REAL    NOT NULL DEFAULT 0,
        pos_y        REAL    NOT NULL DEFAULT 0,
        is_collapsed INTEGER NOT NULL DEFAULT 0 -- 0=expanded, 1=collapsed
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
        name               TEXT    NOT NULL UNIQUE,
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
        project_id    INTEGER NOT NULL REFERENCES Projects(id) ON DELETE CASCADE,
        machine_id    INTEGER NOT NULL REFERENCES Machines(id),
        recipe_id     INTEGER          REFERENCES Recipes(id),
        group_id      INTEGER          REFERENCES Groups(id) ON DELETE SET NULL,
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

