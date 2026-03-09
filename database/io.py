"""
database/io.py
Serialisation logic for exporting/importing projects as JSON files.
Now includes groups alongside nodes and connections.
"""

import json
import logging
from database.crud import (
    get_all_placed_nodes, get_all_connections, get_all_groups,
    add_project, add_placed_node, add_connection, add_group,
    update_group_collapse,
)
from database.db import get_connection

logger = logging.getLogger("satisfactory_planner")


def export_project_to_json(project_id: int, file_path: str) -> bool:
    """Serialize a project's groups, nodes and connections to a JSON file."""
    try:
        conn = get_connection()
        proj = conn.execute("SELECT name FROM Projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            return False

        groups = get_all_groups(project_id)
        nodes = get_all_placed_nodes(project_id)
        connections = get_all_connections(project_id)

        data = {
            "version": 2,
            "project_name": proj["name"],
            "groups": groups,
            "nodes": nodes,
            "connections": connections
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        
        logger.info("[IO] Project '%s' exported to %s", proj["name"], file_path)
        return True
    except Exception as e:
        logger.error("[IO] Export failed: %s", e)
        return False


def import_project_from_json(file_path: str) -> int | None:
    """Load a project from JSON and insert it as a new project in the DB."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "nodes" not in data:
            return None

        # 1. Create new project entry with unique name
        base_name = data.get("project_name", "Imported Project")
        conn = get_connection()
        name = base_name
        counter = 1
        while conn.execute("SELECT 1 FROM Projects WHERE name = ?", (name,)).fetchone():
            name = f"{base_name} ({counter})"
            counter += 1

        new_project_id = add_project(name)

        # 2. Import Groups (if present in file)
        group_id_map = {}  # old_group_id -> new_group_id
        for g in data.get("groups", []):
            old_id = g["id"]
            new_gid = add_group(
                project_id=new_project_id,
                name=g.get("name", "Group"),
                x=g.get("pos_x", 0),
                y=g.get("pos_y", 0),
            )
            if g.get("is_collapsed"):
                update_group_collapse(new_gid, True)
            group_id_map[old_id] = new_gid

        # 3. Import Nodes
        node_id_map = {}  # old_node_id -> new_node_id
        for n in data["nodes"]:
            old_id = n["id"]
            old_group = n.get("group_id")
            new_group = group_id_map.get(old_group) if old_group else None
            
            new_id = add_placed_node(
                project_id=new_project_id,
                machine_id=n["machine_id"],
                recipe_id=n.get("recipe_id"),
                pos_x=n["pos_x"],
                pos_y=n["pos_y"],
                clock_speed=n.get("clock_speed", 1.0),
                group_id=new_group,
            )
            node_id_map[old_id] = new_id

        # 4. Import Connections
        for c in data.get("connections", []):
            new_src = node_id_map.get(c["source_node_id"])
            new_tgt = node_id_map.get(c["target_node_id"])

            if new_src and new_tgt:
                add_connection(
                    source_node_id=new_src,
                    target_node_id=new_tgt,
                    source_port_idx=c.get("source_port_idx", 0),
                    target_port_idx=c.get("target_port_idx", 0),
                    material_id=c.get("material_id")
                )

        logger.info("[IO] Project imported as '%s' from %s", name, file_path)
        return new_project_id
    except Exception as e:
        logger.error("[IO] Import failed: %s", e)
        return None
