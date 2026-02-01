
import streamlit as st
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import numpy as np
import time
import plotly.graph_objects as go

# --- 3D VISUALIZATION (from threed_graph.py) ---

def generate_3d_topology(link_mapping, active_congestion=None, active_link_status=None):
    """
    Generates a 3D aesthetic topology figure using Plotly.
    link_mapping: Dict[str, List[int]] (Link ID -> List of Cell IDs)
    active_congestion: Dict[int, int] (Cell ID -> Congestion Level 0,1,2)
    active_link_status: Dict[str, int] (Link ID -> Congestion Level 0,1,2) - Optional override for CSRs
    """
    G = nx.Graph()
    
    # 1. Define Fixed Hierarchy Nodes (Standard Fronthaul Architecture)
    G.add_node("DU", type="core", group="Core", label="Distributed Unit (DU)")
    G.add_node("Leaf_Switch", type="switch", group="Core", label="Leaf Switch")
    G.add_edge("DU", "Leaf_Switch")
    
    # 2. Create CSR nodes for EACH link in link_mapping (Link_1, Link_2, Link_3)
    link_ids = sorted(link_mapping.keys())  # e.g. ['Link_1', 'Link_2', 'Link_3']
    
    for link_id in link_ids:
        csr_id = f"CSR_{link_id}"
        G.add_node(csr_id, type="csr", group=link_id, label=f"CSR ({link_id})")
        G.add_edge("Leaf_Switch", csr_id)
    
    # Calculate Node Congestion States (Bottom-Up Propagation)
    node_congestion = {}  # node_id -> level (0,1,2)
    
    # 3. Add RUs and Cells per Link
    ru_counter = 1
    for link_id in link_ids:
        cells = link_mapping[link_id]
        csr_id = f"CSR_{link_id}"
        
        # Init Cells congestion
        for cell in cells:
            lvl = 0
            if active_congestion:
                lvl = active_congestion.get(cell, 0)
            node_congestion[f"Cell_{cell}"] = lvl
        
        # Group cells into RUs (4 cells per RU)
        cell_chunks = [cells[i:i + 4] for i in range(0, len(cells), 4)]
        
        for cells_in_ru in cell_chunks:
            ru_id = f"RU_{ru_counter}"
            ru_counter += 1
            
            G.add_node(ru_id, type="ru", group=link_id, label=f"Radio Unit {ru_counter-1}")
            G.add_edge(csr_id, ru_id)
            
            ru_max = 0
            for cell in cells_in_ru:
                cell_node = f"Cell_{cell}"
                G.add_node(cell_node, type="cell", group=link_id, label=f"Cell {cell}")
                G.add_edge(ru_id, cell_node)
                ru_max = max(ru_max, node_congestion.get(cell_node, 0))
            
            node_congestion[ru_id] = ru_max
        
        # CSR Congestion Logic:
        # If we have calculated Link Status (from App aggregation), use that.
        # Otherwise, fallback to Max Propagation from RUs.
        if active_link_status and link_id in active_link_status:
            node_congestion[csr_id] = active_link_status[link_id]
        else:
            csr_max = 0
            for neighbor in G.neighbors(csr_id):
                if G.nodes[neighbor]["type"] == "ru":
                    csr_max = max(csr_max, node_congestion.get(neighbor, 0))
            node_congestion[csr_id] = csr_max
    
    # Propagate to Leaf Switch and DU
    sw_max = max([node_congestion.get(f"CSR_{l}", 0) for l in link_ids], default=0)
    node_congestion["Leaf_Switch"] = sw_max
    node_congestion["DU"] = sw_max


    # 4. Compute 3D Layout (Structured Radial Hierarchical)
    pos = {}
    
    # A) Core Layer (Top)
    pos["DU"] = np.array([0, 0, 3.0])
    pos["Leaf_Switch"] = np.array([0, 0, 2.5])
    
    # B) Link Distribution (CSRs)
    # Distribute links in a perfect circle
    num_links = len(link_ids)
    radius_csr = 1.5
    
    for i, link_id in enumerate(link_ids):
        # Calculate angle for this link branch
        # Phase shift to make Link 1 start at 12 o'clock if possible, or simple division
        theta = (2 * np.pi * i) / num_links
        
        csr_x = radius_csr * np.cos(theta)
        csr_y = radius_csr * np.sin(theta)
        csr_z = 2.0
        
        csr_node = f"CSR_{link_id}"
        pos[csr_node] = np.array([csr_x, csr_y, csr_z])
        
        # C) RU Distribution (Middle Layer)
        # Find RUs strictly belonging to this CSR group
        rus = [n for n in G.neighbors(csr_node) if G.nodes[n].get("type") == "ru"]
        num_rus = len(rus)
        
        if num_rus > 0:
            # Place RUs in an arc centered on the CSR's angle
            # We constrain the arc so branches don't overlap
            max_arc_width = np.pi / 2 if num_links <= 2 else (2 * np.pi / num_links) * 0.7
            
            radius_ru = 3.0  # wider radius for RUs
            
            for j, ru in enumerate(rus):
                # Calculate relative angle offset within the branch sector
                if num_rus == 1:
                    angle_offset = 0
                else:
                    # Linspace between -arc/2 and +arc/2
                    angle_offset = np.linspace(-max_arc_width/2, max_arc_width/2, num_rus)[j]
                
                ru_theta = theta + angle_offset
                ru_x = radius_ru * np.cos(ru_theta)
                ru_y = radius_ru * np.sin(ru_theta)
                ru_z = 1.0
                pos[ru] = np.array([ru_x, ru_y, ru_z])
                
                # D) Cell Distribution (Bottom Layer)
                cells = [n for n in G.neighbors(ru) if G.nodes[n].get("type") == "cell"]
                num_cells = len(cells)
                
                if num_cells > 0:
                    radius_cell_local = 0.4  # Tight cluster around RU
                    for k, cell in enumerate(cells):
                        # Circle around the RU position
                        cell_theta_local = (2 * np.pi * k) / num_cells
                        cell_x = ru_x + radius_cell_local * np.cos(cell_theta_local)
                        cell_y = ru_y + radius_cell_local * np.sin(cell_theta_local)
                        cell_z = 0.0
                        pos[cell] = np.array([cell_x, cell_y, cell_z])
    
    # 5. Create Traces by Group (For Legend & Styling)
    traces = []
    
    # --- EDGE COLORING HELPER ---
    def get_edge_level(u, v):
        # Edge level is the max congestion of its endpoints
        # Usually dominated by the downstream node in a tree
        return max(node_congestion.get(u,0), node_congestion.get(v,0))

    # --- EDGES (Split by Congestion Level) ---
    for level, color, name, width in [
        (0, '#444444', 'Healthy Links', 3),
        (1, '#ff7f0e', 'Warning Links', 5),
        (2, '#ff0000', 'Congested Links (Critical)', 8)
    ]:
        edge_x, edge_y, edge_z = [], [], []
        found = False
        for edge in G.edges():
            lvl = get_edge_level(edge[0], edge[1])
            if lvl == level:
                found = True
                x0, y0, z0 = pos[edge[0]]
                x1, y1, z1 = pos[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
                edge_z.extend([z0, z1, None])
        
        if found:
            traces.append(go.Scatter3d(
                x=edge_x, y=edge_y, z=edge_z,
                mode='lines',
                name=name,
                line=dict(color=color, width=width),
                opacity=0.7 if level==0 else 1.0,
                hoverinfo='none',
                showlegend=True
            ))

    # --- DATA FLOW SIMULATION (Congestion Aware) ---
    for level, color, name, size in [
        (0, '#00f3ff', 'Flow (Normal)', 3),
        (1, '#ffaa00', 'Flow (High Load)', 5),
        (2, '#ffffff', 'Flow (DROPPED)', 6) # White flashes for drops
    ]:
        flow_x, flow_y, flow_z = [], [], []
        found = False
        for edge in G.edges():
            lvl = get_edge_level(edge[0], edge[1])
            if lvl == level:
                found = True
                x0, y0, z0 = pos[edge[0]]
                x1, y1, z1 = pos[edge[1]]
                # Interpolate points
                steps = 5
                for s in range(1, steps):
                    ratio = s / steps
                    flow_x.append(x0 + (x1-x0)*ratio)
                    flow_y.append(y0 + (y1-y0)*ratio)
                    flow_z.append(z0 + (z1-z0)*ratio)
        
        if found:
            traces.append(go.Scatter3d(
                x=flow_x, y=flow_y, z=flow_z,
                mode='markers',
                name=name,
                marker=dict(size=size, color=color, opacity=0.8),
                hoverinfo='none',
                showlegend=True
            ))

    # --- NODES (Categorized) ---
    # Define categories properties
    categories = {
        "core":  {"color": "#00ff00", "size": 30, "symbol": "diamond", "name": "Centralized Unit (DU)"},
        "switch": {"color": "#3498db", "size": 25, "symbol": "square", "name": "Leaf Switch"},
        "csr":    {"color": "#e67e22", "size": 20, "symbol": "circle", "name": "CSR (Aggregator)"},
        "ru":     {"color": "#9b59b6", "size": 15, "symbol": "circle", "name": "Radio Unit (RU)"},
        "cell":   {"color": "#bdc3c7", "size": 8,  "symbol": "circle", "name": "Cell Site"}
    }
    
    # Bucket nodes
    node_groups = {k: {"x": [], "y": [], "z": [], "text": []} for k in categories}
    
    for node in G.nodes():
        params = node_groups[G.nodes[node]["type"]]
        x, y, z = pos[node]
        params["x"].append(x)
        params["y"].append(y)
        params["z"].append(z)
        params["text"].append(G.nodes[node].get("label", node))

    # Create a trace for each category
    for cat_type, data in node_groups.items():
        if not data["x"]: continue
        
        style = categories[cat_type]
        
        # Show text labels for non-cell nodes to reduce clutter
        mode = 'markers+text' if cat_type != 'cell' else 'markers'
        
        traces.append(go.Scatter3d(
            x=data["x"], y=data["y"], z=data["z"],
            mode=mode,
            name=style["name"],
            marker=dict(
                size=style["size"],
                color=style["color"],
                symbol=style.get("symbol", "circle"),
                line=dict(color='#ffffff', width=2),
                opacity=1.0
            ),
            text=data["text"],
            textposition="top center",
            textfont=dict(color="#ffffff", size=10) if cat_type != 'cell' else None,
            hoverinfo='text'
        ))

    # 6. Layout
    fig = go.Figure(data=traces)
    
    fig.update_layout(
        title="✨ 3D Network Topology & Data Flow",
        title_font_color="#ffffff",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        showlegend=True,
        legend=dict(
            x=0.75,
            y=0.1,
            title_text="Network Elements",
            font=dict(color="#ffffff"),
            bgcolor="rgba(0,0,0,0.5)",
            bordercolor="#444",
            borderwidth=1
        ),
        scene=dict(
            xaxis=dict(showbackground=True, visible=True, gridcolor="#333", title="X"),
            yaxis=dict(showbackground=True, visible=True, gridcolor="#333", title="Y"),
            zaxis=dict(showbackground=True, visible=True, gridcolor="#333", title="Z"),
            bgcolor="#0e1117"
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=700
    )
    # Identify Congested Elements for Report
    congested_elements = []
    for node, level in node_congestion.items():
        if level > 0:
            label = G.nodes[node].get("label", node)
            congested_elements.append({"node": label, "level": level})
            
    return fig, congested_elements

# --- 2D ANIMATION UTILS (from graph_frames.py) ---

COLOR_MAP = {
    0: "#2ca02c", # Green (Normal)
    1: "#ff7f0e", # Orange (Mild)
    2: "#d62728"  # Red (Severe)
}

SIZE_MAP = {
    0: 300,
    1: 450,
    2: 600
}

def draw_network_frame(G, pos, active_congestion, current_slot, ax=None):
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 8))
    else:
        fig = ax.figure

    ax.clear()
    
    node_colors = []
    node_sizes = []
    
    for node in G.nodes():
        node_type = G.nodes[node].get("type", "cell")
        
        if node_type == "link":
            node_colors.append("#7f7f7f")
            node_sizes.append(400)
            continue
            
        # Extract Cell ID from "Cell_X"
        try:
            cell_id = int(str(node).replace("Cell_", ""))
            level = active_congestion.get(cell_id, 0)
        except:
            level = 0
            
        node_colors.append(COLOR_MAP.get(level, "#2ca02c"))
        node_sizes.append(SIZE_MAP.get(level, 300))

    edge_colors = []
    edge_widths = []
    
    for u, v in G.edges():
        # Simplification: Edges color based on the cell node
        # Assume u or v is the cell
        cell_node = u if "Cell_" in str(u) else v
        try:
            cell_id = int(str(cell_node).replace("Cell_", ""))
            level = active_congestion.get(cell_id, 0)
        except:
            level = 0
            
        if level == 2:
            edge_colors.append("#d62728")
            edge_widths.append(3.0)
        elif level == 1:
            edge_colors.append("#ff7f0e")
            edge_widths.append(2.0)
        else:
            edge_colors.append("#cccccc") 
            edge_widths.append(1.0)

    nx.draw_networkx_nodes(
        G, pos, 
        node_size=node_sizes, 
        node_color=node_colors, 
        edgecolors="white", 
        linewidths=1.5,
        ax=ax
    )
    
    nx.draw_networkx_edges(
        G, pos, 
        edge_color=edge_colors, 
        width=edge_widths,
        ax=ax
    )
    
    labels = {}
    for node in G.nodes():
        if G.nodes[node].get("type") == "link":
            labels[node] = node
        else:
            labels[node] = str(node).replace("Cell_", "")
    
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_color="#333", ax=ax)
    
    ax.set_title(f"Simulation Time: Slot {current_slot}", fontsize=14, loc='left')
    ax.axis('off')
    
    return fig

# --- ANIMATION CONTROLLER (from animate.py) ---

def render_simulation_ui(G, pos, congestion_state):
    st.markdown("### 🚦 Fronthaul Congestion Propagation Simulator")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        run_sim = st.button("▶️ Play Simulation")
        stop_sim = st.button("⏹️ Stop")
        
    with col2:
        speed = st.slider("Animation Speed (sec/frame)", 0.05, 1.0, 0.1, 0.05)
        
    with col3:
        min_slot = int(congestion_state.index.min())
        max_slot = int(congestion_state.index.max())
        # Default to a small window to avoid overwhelming
        if max_slot > min_slot:
            start_slot, end_slot = st.slider(
                "Time Window", 
                min_slot, max_slot, 
                (min_slot, min(min_slot + 50, max_slot))
            )
        else:
            st.info(f"Single time slot detected: {min_slot}")
            start_slot, end_slot = min_slot, max_slot

    plot_placeholder = st.empty()
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Draw Initial Frame
    if start_slot in congestion_state.index:
        init_state = congestion_state.loc[start_slot].to_dict()
    else:
        init_state = {}
        
    draw_network_frame(G, pos, init_state, start_slot, ax=ax)
    plot_placeholder.pyplot(fig)
    
    if run_sim:
        for slot in range(start_slot, end_slot + 1):
            if stop_sim:
                break
            
            if slot in congestion_state.index:
                current_state = congestion_state.loc[slot].to_dict()
            else:
                current_state = {}
                
            draw_network_frame(G, pos, current_state, slot, ax=ax)
            plot_placeholder.pyplot(fig)
            time.sleep(speed)
            
        st.success("Simulation Complete")

def prepare_congestion_data(df):
    """
    Converts raw dataframe to congestion state matrix (0, 1, 2).
    """
    # 1. Pivot: Index=Slot, Col=Cell, Val=Gbps
    pivot = df.pivot_table(index='slot_idx', columns='cell_id', values='gbps', fill_value=0)
    
    # Check if we have packet loss data
    has_loss_data = 'packet_loss' in df.columns and df['packet_loss'].max() > 0
    
    congestion = pivot.copy()
    
    # Check if we have systematic congestion score
    if 'congestion_score' in df.columns and df['congestion_score'].max() > 0:
        score_pivot = df.pivot_table(index='slot_idx', columns='cell_id', values='congestion_score', fill_value=0)
        
        # User defined thresholds:
        # Score < 0.02 → Healthy (0)
        # 0.02 - 0.05 → Moderate (1)
        # > 0.05 → Heavy/Critical (2)
        
        congestion[:] = 0
        congestion[score_pivot > 0.02] = 1
        congestion[score_pivot > 0.05] = 2
        
    elif has_loss_data:
        # Pivot loss data directly
        loss_pivot = df.pivot_table(index='slot_idx', columns='cell_id', values='packet_loss', fill_value=0)
        
        # Level 0: No Loss
        # Level 1: Low Loss (1-4 packets)
        # Level 2: High Loss (>4 packets)
        congestion[:] = 0
        congestion[loss_pivot > 0] = 1
        congestion[loss_pivot > 4] = 2
    else:
        # Fallback to throughput inference if no packet data
        # Assume 2.5 Gbps is "High" for a single cell (simplification)
        congestion[pivot < 1.0] = 0
        congestion[(pivot >= 1.0) & (pivot < 2.0)] = 1
        congestion[pivot >= 2.0] = 2
    
    return congestion.astype(int)
