"""
database/io.py
Serialisation logic for exporting/importing projects as JSON files.
"""

import json
import os
from database.crud import (
    get_all_placed_nodes, get_all_connections, add_project,
    add_placed_node, add_connection, get_connection
)

def export_project_to_json(project_id: int, file_path: str) -> bool:
    """Serialize a project's nodes and connections to a JSON file."""
    try:
        # 1. Fetch project name
        conn = get_connection()
        proj = conn.execute("SELECT name FROM Projects WHERE id = ?", (project_id,)).fetchone()
        if not proj:
            return False
            
        # 2. Fetch all nodes
        nodes = get_all_placed_nodes(project_id)
        # 3. Fetch all connections
        connections = get_all_connections(project_id)
        
        data = {
            "version": 1,
            "project_name": proj["name"],
            "nodes": nodes,
            "connections": connections
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"[IO] Export failed: {e}")
        return False

def import_project_from_json(file_path: str) -> int | None:
    """Load a project from JSON and insert it as a new project in the DB."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        if "nodes" not in data:
            return None
            
        # 1. Create new project entry
        base_name = data.get("project_name", "Imported Project")
        # Ensure unique name
        conn = get_connection()
        name = base_name
        counter = 1
        while conn.execute("SELECT 1 FROM Projects WHERE name = ?", (name,)).fetchone():
            name = f"{base_name} ({counter})"
            counter += 1
            
        new_project_id = add_project(name)
        
        # 2. Map old IDs to new ones
        node_id_map = {} # old_node_id -> new_node_id
        
        for n in data["nodes"]:
            old_id = n["id"]
            new_id = add_placed_node(
                project_id=new_project_id,
                machine_id=n["machine_id"],
                recipe_id=n.get("recipe_id"),
                pos_x=n["pos_x"],
                pos_y=n["pos_y"],
                clock_speed=n.get("clock_speed", 1.0)
            )
            node_id_map[old_id] = new_id
            
        # 3. Add connections
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
                
        return new_project_id
    except Exception as e:
        print(f"[IO] Import failed: {e}")
        return None
