"""
database/db.py
Manages the SQLite connection, table initialization, and schema migrations.
"""

import sqlite3
import os
import logging

# Configure logging
logger = logging.getLogger("satisfactory_planner")

# The .db file lives at the project root
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "satisfactory.db")
_connection: sqlite3.Connection | None = None

# Current schema version — increment when adding migrations
_SCHEMA_VERSION = 3


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


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Read the current schema version from the DB. Returns 0 if not set."""
    try:
        row = conn.execute("SELECT value FROM Settings WHERE key = 'schema_version'").fetchone()
        return int(row["value"]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Store the current schema version in the Settings table."""
    conn.execute(
        "INSERT INTO Settings (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),)
    )


def initialize_db() -> None:
    """Create all tables if they do not exist and run any pending migrations."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Core schema (idempotent with IF NOT EXISTS) ──────────────────
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

    -- Logical groups of machines
    CREATE TABLE IF NOT EXISTS Groups (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id   INTEGER NOT NULL REFERENCES Projects(id) ON DELETE CASCADE,
        name         TEXT    NOT NULL,
        pos_x        REAL    NOT NULL DEFAULT 0,
        pos_y        REAL    NOT NULL DEFAULT 0,
        is_collapsed INTEGER NOT NULL DEFAULT 0 -- 0=expanded, 1=collapsed
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

    # ── Ensure a default project exists ──────────────────────────────
    if not conn.execute("SELECT 1 FROM Projects LIMIT 1").fetchone():
        conn.execute("INSERT INTO Projects (id, name) VALUES (1, 'Default Project')")

    # ── Apply incremental migrations ─────────────────────────────────
    version = _get_schema_version(conn)

    if version < _SCHEMA_VERSION:
        logger.info("[DB] Migrating schema from v%d to v%d", version, _SCHEMA_VERSION)
        # Future migrations go here as:
        # if version < 4:
        #     cursor.execute("ALTER TABLE ... ADD COLUMN ...")
        _set_schema_version(conn, _SCHEMA_VERSION)

    conn.commit()
    logger.info("[DB] Tables initialized (Schema v%d).", _SCHEMA_VERSION)
