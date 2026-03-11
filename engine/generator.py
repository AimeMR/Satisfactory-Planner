"""
engine/generator.py
Logic for automatically generating a production line from a target material backwards to raw resources.
"""

from typing import Any
import math
import random

from database.crud import (
    get_all_machines, get_all_recipes, get_all_materials,
    add_placed_node, add_connection
)

class GeneratorNode:
    def __init__(self, recipe: dict | None, material_id: int, target_rate: float,
                 group_name: str = "Group"):
        self.recipe = recipe
        self.material_id = material_id
        self.target_rate = target_rate
        self.group_name = group_name
        self.machines = []  # List of dicts: {"machine_id": int, "clock_speed": float}
        self.inputs = []    # List of GeneratorNode
        
        # Generated DB nodes
        self.db_ids = []
        self.x = 0
        self.y = 0

def generate_production_line(project_id: int, final_material_id: int, target_rate: float) -> bool:
    """
    Generate an entire production line to produce `target_rate` of `final_material_id`.
    Writes directly to the DB under `project_id`.
    """
    
    # 1. Fetch data
    recipes = get_all_recipes()
    machines = get_all_machines()
    materials = {m["id"]: m["name"] for m in get_all_materials()}
    
    # Helper to find a recipe that produces a given material
    def find_recipe_for(mat_id: int) -> dict | None:
        # Avoid un-craftable recipes or alternate recipes if possible
        # We just pick the first standard recipe that outputs this material.
        for r in recipes:
            for ing in r.get("materials", []):
                if ing["material_id"] == mat_id and not ing["is_input"]:
                    return r
        return None

    def build_graph(mat_id: int, rate: float) -> GeneratorNode:
        recipe = find_recipe_for(mat_id)
        mat_name = materials.get(mat_id, f"Mat_{mat_id}")
        
        node = GeneratorNode(recipe, mat_id, rate, group_name=mat_name)
        
        if not recipe:
            # We assume it's a raw material (like Iron Ore) and needs an extractor.
            # Find a miner/extractor machine
            miner_machine = next((m for m in machines if m["category"] == "Extraction"), machines[0])
            
            # Assuming a Mk.1 miner extracts 60/min as base (a crude approximation since DB recipes for miners don't exist in same way)
            base_rate = 60.0
            num_machines = math.ceil(rate / base_rate)
            for i in range(num_machines):
                clock = 1.0
                if i == num_machines - 1:
                    remainder = rate - (i * base_rate)
                    clock = remainder / base_rate
                node.machines.append({"machine_id": miner_machine["id"], "clock_speed": clock})
                
            return node
            
        # If there is a recipe, calculate how many machines we need
        craft_time = recipe["craft_time"]
        # Find how much output this recipe makes of the target material
        output_ing = next((ing for ing in recipe["materials"] if ing["material_id"] == mat_id and not ing["is_input"]), None)
        output_amount = output_ing["amount"] if output_ing else 1.0
        
        base_rate_per_min = (output_amount / craft_time) * 60.0
        
        num_machines = math.ceil(rate / base_rate_per_min)
        for i in range(num_machines):
            clock = 1.0
            if i == num_machines - 1 and num_machines > 0:
                remainder = rate - (i * base_rate_per_min)
                clock = remainder / base_rate_per_min
            node.machines.append({"machine_id": recipe["machine_id"], "clock_speed": clock})
        
        # Recurse for inputs
        for ing in recipe["materials"]:
            if ing["is_input"]:
                input_mat_id = ing["material_id"]
                input_amount = ing["amount"]
                
                # We need `rate` total output.
                # Recipe ratio: input_amount needed per output_amount created
                required_input_rate = (input_amount / output_amount) * rate
                
                child_node = build_graph(input_mat_id, required_input_rate)
                node.inputs.append(child_node)
                
        return node
        
    print(f"Building graph for {final_material_id} at {target_rate}/min...")
    root = build_graph(final_material_id, target_rate)
    
    # 2. Layout Graph (Simple X coordinates based on depth, Y based on siblings)
    def calculate_depth(node: GeneratorNode) -> int:
        if not node.inputs:
            return 0
        return 1 + max(calculate_depth(i) for i in node.inputs)
        
    max_depth = calculate_depth(root)
    
    X_SPACING = 300
    Y_SPACING = 150
    
    # assign coords recursively
    def assign_coords(node: GeneratorNode, depth: int, y_offset: float) -> float:
        # Place node
        node.x = (max_depth - depth) * X_SPACING
        node.y = y_offset
        
        # Return next y_offset
        current_y = y_offset
        for i, child in enumerate(node.inputs):
            current_y = assign_coords(child, depth + 1, current_y)
        
        # Shift ourselves to be centered vertically relative to our children
        if node.inputs:
            node.y = (node.inputs[0].y + node.inputs[-1].y) / 2.0
            
        # Account for our own height
        my_height = len(node.machines) * Y_SPACING
        return max(y_offset + my_height, current_y)

    assign_coords(root, 0, 0.0)

    # 3. Create elements in DB
    from database.crud import add_group
    
    # Flatten graph to create them
    connections_to_make = [] # (source_node_id, target_node_id, source_port, target_port, material_id)
    
    # Pre-fetch logistics machines
    splitter_machine = next((m for m in machines if m["name"] == "Splitter"), None)
    merger_machine = next((m for m in machines if m["name"] == "Merger"), None)

    def persist_node(node: GeneratorNode):
        # Create group
        gid = add_group(project_id, f"{node.group_name} ({node.target_rate:.1f}/min)", node.x, node.y)
        
        # Create machines
        for i, m_info in enumerate(node.machines):
            m_y = node.y + (i * 120)
            db_id = add_placed_node(project_id, m_info["machine_id"], 
                                    node.recipe["id"] if node.recipe else None,
                                    node.x, m_y, m_info["clock_speed"], gid)
            node.db_ids.append(db_id)
            
        for child in node.inputs:
            persist_node(child)
            
            # Map child.db_ids (sources producing material) to node.db_ids (targets consuming material)
            if not child.db_ids or not node.db_ids:
                continue
                
            sources = child.db_ids
            targets = node.db_ids
            mat_id = child.material_id
            
            # Determine which input port index this material belongs to on the TARGET node's recipe
            target_port_idx = 0
            if node.recipe:
                # Recipes list ingredients. The input port index visually matches the order of inputs.
                inputs_only = [ing for ing in node.recipe["materials"] if ing["is_input"]]
                # Sort them (assume UI sorted by ID or original order, but let's just use index in list)
                for port_i, ing in enumerate(inputs_only):
                    if ing["material_id"] == mat_id:
                        target_port_idx = port_i
                        break
            
            # M:N mapping using Mergers/Splitters if sizes differ
            if len(sources) == 1 and len(targets) == 1:
                # 1:1 direct connection
                connections_to_make.append((sources[0], targets[0], 0, target_port_idx, mat_id))
                
            elif len(sources) == 1 and len(targets) > 1 and splitter_machine:
                # 1:N -> Need a Splitter
                sp_x = node.x - 150
                sp_y = node.y + ((len(targets) * 120) / 2) - 60
                sp_id = add_placed_node(project_id, splitter_machine["id"], None, sp_x, sp_y, 1.0, None)
                
                # Connect source to splitter input 0
                connections_to_make.append((sources[0], sp_id, 0, 0, mat_id))
                
                # Connect splitter outputs to targets
                for i, target_id in enumerate(targets):
                    # Splitters have 3 outputs in our DB usually, reuse if more than 3
                    out_port = i % 3
                    connections_to_make.append((sp_id, target_id, out_port, target_port_idx, mat_id))
                    
            elif len(sources) > 1 and len(targets) == 1 and merger_machine:
                # N:1 -> Need a Merger
                mg_x = child.x + 150
                mg_y = child.y + ((len(sources) * 120) / 2) - 60
                mg_id = add_placed_node(project_id, merger_machine["id"], None, mg_x, mg_y, 1.0, None)
                
                # Connect sources to merger inputs
                for i, source_id in enumerate(sources):
                    in_port = i % 3
                    connections_to_make.append((source_id, mg_id, 0, in_port, mat_id))
                    
                # Connect merger output 0 to target
                connections_to_make.append((mg_id, targets[0], 0, target_port_idx, mat_id))
                
            elif len(sources) > 1 and len(targets) > 1 and merger_machine and splitter_machine:
                # N:M -> Merge all to 1, then Split to M
                mg_x = child.x + 100
                mg_y = child.y + ((len(sources) * 120) / 2) - 60
                mg_id = add_placed_node(project_id, merger_machine["id"], None, mg_x, mg_y, 1.0, None)
                
                # Sources -> Merger
                for i, source_id in enumerate(sources):
                    in_port = i % 3
                    connections_to_make.append((source_id, mg_id, 0, in_port, mat_id))
                
                sp_x = node.x - 100
                sp_y = node.y + ((len(targets) * 120) / 2) - 60
                sp_id = add_placed_node(project_id, splitter_machine["id"], None, sp_x, sp_y, 1.0, None)
                
                # Merger -> Splitter
                connections_to_make.append((mg_id, sp_id, 0, 0, mat_id))
                
                # Splitter -> Targets
                for i, target_id in enumerate(targets):
                    out_port = i % 3
                    connections_to_make.append((sp_id, target_id, out_port, target_port_idx, mat_id))
                    
            else:
                # Fallback: simple zip pairing if missing splitters/mergers
                for i, target_id in enumerate(targets):
                    source_id = sources[i % len(sources)]
                    connections_to_make.append((source_id, target_id, 0, target_port_idx, mat_id))

    persist_node(root)
    
    for src, tgt, s_idx, t_idx, mat in connections_to_make:
        add_connection(src, tgt, s_idx, t_idx, mat)
        
    return True

