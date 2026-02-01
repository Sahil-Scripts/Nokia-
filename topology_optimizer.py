
import pandas as pd
import numpy as np
import random
import time
import streamlit as st

# Cost Table (same as app.py)
# CAPEX Cost Estimates (INR per link - Typical Operator Pricing in India)
# Approx conversion ~85 INR/USD + taxes
# Default values (fallback)
DEFAULT_LINK_COSTS = {
    1: 45000,
    10: 170000,
    25: 680000,
    40: 1275000,
    100: 2975000
}
LINK_SPEEDS = [1, 10, 25, 40, 100]

def get_required_speed(gbps_val):
    for speed in LINK_SPEEDS:
        if gbps_val <= speed * 0.8:  # 80% utilization rule
            return speed
    return 100

    return 100

def calculate_topology_cost(df, mapping, slot_duration=0.0005, gbps_scale=1e9, link_costs=None):
    """
    Calculates the total CAPEX for a given cell-to-link mapping.
    """
    # Map cells to links
    df_copy = df.copy()
    df_copy['link_id'] = df_copy['cell_id'].map(mapping)
    
    # 2. Aggregate traffic per link
    # groupby link and time, sum bits
    link_traffic = df_copy.groupby(['link_id', 'slot_idx'])['bits'].sum().reset_index()
    
    # 3. Calculate max Gbps for each link
    total_cost = 0
    link_details = {}
    
    for link_id in mapping.values():
        if link_id not in link_details: # Process each link once
            # Get data for this link
            l_data = link_traffic[link_traffic['link_id'] == link_id]
            if l_data.empty:
                peak_gbps = 0
            else:
                max_bits = l_data['bits'].max()
                peak_gbps = (max_bits / slot_duration) / gbps_scale
            
            req_speed = get_required_speed(peak_gbps)
            if link_costs is None:
                link_costs = DEFAULT_LINK_COSTS
                
            cost = link_costs[req_speed]
            total_cost += cost
            link_details[link_id] = {'peak': peak_gbps, 'speed': req_speed, 'cost': cost}
            
    return total_cost, link_details

def optimize_topology(df, num_links=3, iterations=200, link_costs=None):
    """
    Tries random permutations to find a topology with lower Total CAPEX.
    Maximizes statistical multiplexing by grouping non-overlapping peaks.
    """
    unique_cells = df['cell_id'].unique().tolist()
    
    best_mapping = {}
    best_cost = float('inf')
    best_details = {}
    
    # Ensure slot_idx exists
    slot_duration = 0.0005
    if 'slot_idx' not in df.columns:
        min_time = df['time'].min()
        df['slot_idx'] = ((df['time'] - min_time) / slot_duration).astype(int)
        
    start_time = time.time()
    
    # Try random assignments
    for i in range(iterations):
        # Shuffle cells
        random.shuffle(unique_cells)
        
        # Split into roughly equal groups
        # (This is a simplification, we could also vary group sizes, but let's assume balanced load is generally good)
        chunk_size = -(-len(unique_cells) // num_links) # Ceiling division
        
        current_mapping = {}
        for idx, cell in enumerate(unique_cells):
            link_num = (idx // chunk_size) + 1
            # Ensure we don't exceed num_links (for uneven splits)
            if link_num > num_links: link_num = num_links
            current_mapping[cell] = f"Link_{link_num}"
            
        # Calculate Cost
        cost, details = calculate_topology_cost(df, current_mapping, link_costs=link_costs)
        
        if cost < best_cost:
            best_cost = cost
            best_mapping = current_mapping.copy()
            best_details = details
            
    return best_mapping, best_cost, best_details
