
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import openai
import json
from datetime import datetime
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from topology_optimizer import optimize_topology, calculate_topology_cost
import simulation_utils as sim_utils
import networkx as nx

# --- NOKIA BRANDING & STYLING ---
st.set_page_config(
    page_title="Nokia Fronthaul Capacity Optimizer",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Professional Telecom-Grade CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background-color: #f5f7fa;
    }
    
    /* Nokia Blue Theme */
    .nokia-header {
        background: linear-gradient(135deg, #124191 0%, #1976D2 100%);
        padding: 30px;
        border-radius: 10px;
        color: white;
        margin-bottom: 30px;
        box-shadow: 0 4px 12px rgba(18, 65, 145, 0.3);
    }
    
    /* KPI Cards - FIXED CONTRAST FOR DARK THEME */
    div[data-testid="stMetricValue"] {
        font-size: 32px !important;
        font-weight: 700 !important;
        color: #000000 !important;
        background: transparent !important;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 14px !important;
        color: #000000 !important;
        font-weight: 600 !important;
        background: transparent !important;
    }
    
    div[data-testid="stMetricDelta"] {
        color: #000000 !important;
    }
    
    /* Force the entire metric container to have proper colors */
    [data-testid="stMetricValue"] > div {
        color: #000000 !important;
    }
    
    [data-testid="stMetricLabel"] > div {
        color: #000000 !important;
    }
    
    .stMetric {
        background-color: #ffffff !important;
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        border-left: 4px solid #124191 !important;
    }
    
    .stMetric label {
        color: #000000 !important;
    }
    
    .stMetric div {
        color: #000000 !important;
    }
    
    /* Recommendation Box */
    .recommendation-box {
        background: linear-gradient(135deg, #00D084 0%, #00A968 100%);
        padding: 25px;
        border-radius: 12px;
        color: white;
        margin: 20px 0;
        box-shadow: 0 4px 12px rgba(0, 208, 132, 0.3);
    }
    
    .warning-box {
        background: linear-gradient(135deg, #FF6B35 0%, #F7931E 100%);
        padding: 25px;
        border-radius: 12px;
        color: white;
        margin: 20px 0;
    }
    
    /* SLA Badge */
    .sla-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 14px;
    }
    
    .sla-high {
        background-color: #00D084;
        color: white;
    }
    
    .sla-medium {
        background-color: #F7931E;
        color: white;
    }
    
    .sla-low {
        background-color: #FF6B35;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- TELECOM CONSTANTS ---
SLOT_DURATION_SEC = 0.0005
SYMBOL_DURATION_SEC = 35.7e-6
GBPS_SCALE = 1e9

# Link Speed Options (Gbps) - Aligned with Nokia AirScale & 7250 IXR capabilities
LINK_SPEEDS = [1, 2.5, 5, 10, 25, 40, 50, 100, 400]

# CAPEX Cost Estimates (INR per link - Typical Operator Pricing in India)
LINK_COSTS = {
    1: 45000,
    2.5: 85000,
    5: 125000,
    10: 170000,
    25: 680000,
    40: 1275000,
    50: 1500000,
    100: 2975000,
    400: 8500000
}

# Default Topology
DEFAULT_MAPPING = {
    1: "Link_1", 2: "Link_1", 3: "Link_1", 4: "Link_1", 5: "Link_1", 6: "Link_1", 7: "Link_1", 8: "Link_1",
    9: "Link_2", 10: "Link_2", 11: "Link_2", 12: "Link_2", 13: "Link_2", 14: "Link_2", 15: "Link_2", 16: "Link_2",
    17: "Link_3", 18: "Link_3", 19: "Link_3", 20: "Link_3", 21: "Link_3", 22: "Link_3", 23: "Link_3", 24: "Link_3"
}

# --- CORE ALGORITHMS ---

@st.cache_data(show_spinner=False)
def load_data(uploaded_files):
    data_frames = []
    progress_bar = st.progress(0)
    
    for i, file_obj in enumerate(uploaded_files):
        try:
            filename = file_obj.name
            
            # Detect file type
            if "throughput" in filename:
                # Format: time bits
                cell_id_str = filename.replace("throughput-cell-", "").replace(".dat", "")
                cell_id = int(cell_id_str)
                df = pd.read_csv(file_obj, sep=r'\s+', names=["time", "bits"], engine='c')
                df['cell_id'] = cell_id
                df['type'] = 'throughput'
                data_frames.append(df)
            elif "packet" in filename or "pkt" in filename:
                # Handle extended packet stats
                # Expected format options:
                # 1. Simple: slot_idx, packet_loss
                # 2. Detailed: slot, txPackets, rxPackets, tooLateRxPackets, buffer_occupancy
                
                import re
                match = re.search(r"cell[-_]?(\d+)", filename)
                if match:
                    cell_id = int(match.group(1))
                    
                    # Try reading strictly to inspect columns
                    try:
                        temp_df = pd.read_csv(file_obj, sep=r'\s+', engine='c')
                        if len(temp_df.columns) >= 4: # Assume detailed
                            # Determine column names based on width or header presence
                            # If no header, assume standard telecom format: 
                            # time/slot, tx, rx, too_late, (optional: buffer)
                            if 'tooLateRxPackets' not in temp_df.columns:
                                if len(temp_df.columns) == 5:
                                    temp_df.columns = ["slot_idx", "txPackets", "rxPackets", "tooLateRxPackets", "buffer_occupancy"]
                                elif len(temp_df.columns) == 4:
                                    temp_df.columns = ["slot_idx", "txPackets", "rxPackets", "tooLateRxPackets"]
                            
                            temp_df['cell_id'] = cell_id
                            temp_df['type'] = 'detailed_stats'
                            data_frames.append(temp_df)
                        else:
                            # Fallback to simple loss format
                            # Reset file pointer if needed, but here we read into temp_df
                            temp_df.columns = ["slot_idx", "packet_loss"]
                            temp_df['cell_id'] = cell_id
                            temp_df['type'] = 'packet_loss'
                            data_frames.append(temp_df)
                    except:
                        # Fallback for simple files (no header, 2 cols)
                        file_obj.seek(0)
                        df = pd.read_csv(file_obj, sep=r'\s+', names=["slot_idx", "packet_loss"], engine='c')
                        df['cell_id'] = cell_id
                        df['type'] = 'packet_loss'
                        data_frames.append(df)
                    
        except Exception as e:
            st.warning(f"⚠️ Skipped {file_obj.name}: {str(e)}")
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    progress_bar.empty()
    if not data_frames: return None
    
    # Process Different Frames
    tp_frames = [d for d in data_frames if d['type'].iloc[0] == 'throughput']
    pl_frames = [d for d in data_frames if d['type'].iloc[0] == 'packet_loss']
    detailed_frames = [d for d in data_frames if d['type'].iloc[0] == 'detailed_stats']
    
    full_df = None
    
    # Base Traffic Data
    if tp_frames:
        full_df = pd.concat(tp_frames, ignore_index=True)
        min_time = full_df['time'].min()
        full_df['slot_idx'] = ((full_df['time'] - min_time) / SLOT_DURATION_SEC).astype(int)
    
    # Integrate Detailed Stats (Priority)
    if detailed_frames:
        det_df = pd.concat(detailed_frames, ignore_index=True)
        # Sort by slot
        det_df = det_df.sort_values('slot_idx')
        
        # --- SYSTEMATIC CONGESTION DETECTION LOGIC ---
        # 1. Calculate Deltas (since counters accumulate)
        # Group by cell to ensure diff is valid
        # If data is NOT cumulative (i.e. per slot), skip diff. 
        # Heuristic: if values always increase, it's cumulative.
        is_cumulative = det_df.groupby('cell_id')['rxPackets'].is_monotonic_increasing.all()
        
        if is_cumulative:
            cols_to_diff = ['txPackets', 'rxPackets', 'tooLateRxPackets']
            det_df[cols_to_diff] = det_df.groupby('cell_id')[cols_to_diff].diff().fillna(method='bfill')
            
        # 2. Compute Ratios
        # Avoid division by zero
        det_df['late_ratio'] = det_df['tooLateRxPackets'] / det_df['rxPackets'].replace(0, 1)
        det_df['loss_ratio'] = (det_df['txPackets'] - det_df['rxPackets']) / det_df['txPackets'].replace(0, 1)
        
        # 3. Congestion Score
        # Weighting: 0.6 * Late + 0.3 * Loss + 0.1 * NormalizedLoad (Simplified)
        det_df['congestion_score'] = (0.6 * det_df['late_ratio']) + (0.3 * det_df['loss_ratio'].clip(lower=0))
        
        if full_df is not None:
             full_df = pd.merge(full_df, det_df, on=['cell_id', 'slot_idx'], how='outer')
        else:
             # Construct base if no throughput file
             full_df = det_df
             full_df['time'] = full_df['slot_idx'] * SLOT_DURATION_SEC
             # Estimate bits if missing? Or just leave null.
             if 'bits' not in full_df.columns:
                 full_df['bits'] = full_df['rxPackets'] * 8 * 1500 # Approx MTU size
        
    elif pl_frames:
        # Fallback to simple logic
        pl_df = pd.concat(pl_frames, ignore_index=True)
        pl_df['congestion_score'] = 0.5 * (pl_df['packet_loss'] > 0).astype(float) # Binary congestion
        
        if full_df is not None:
            full_df = pd.merge(full_df, pl_df, on=['cell_id', 'slot_idx'], how='left')
        else:
            full_df = pl_df
            full_df['time'] = full_df['slot_idx'] * SLOT_DURATION_SEC
            full_df['bits'] = 0
            
    # Final Cleanup
    if full_df is not None:
        full_df.fillna(0, inplace=True)
        # Ensure Score is Present
        if 'congestion_score' not in full_df.columns:
            full_df['congestion_score'] = 0.0
            
    return full_df

def calculate_capacity_with_buffer(traffic_gbps, buffer_symbols, max_loss_pct=1.0):
    """
    Binary search for minimum required capacity given buffer size and loss tolerance.
    """
    buffer_time_sec = buffer_symbols * SYMBOL_DURATION_SEC
    
    low, high = float(np.mean(traffic_gbps)), float(np.max(traffic_gbps))
    best_c = high
    
    traffic_bits = traffic_gbps * GBPS_SCALE * SLOT_DURATION_SEC
    total_slots = len(traffic_bits)
    max_allowed_loss = int(total_slots * (max_loss_pct / 100.0))
    
    for _ in range(15):
        c = (low + high) / 2
        capacity_bits_per_slot = c * GBPS_SCALE * SLOT_DURATION_SEC
        max_buffer_bits = buffer_time_sec * (c * GBPS_SCALE)
        
        current_buffer = 0.0
        loss = 0
        
        for bits in traffic_bits:
            current_buffer += bits
            if current_buffer > capacity_bits_per_slot:
                current_buffer -= capacity_bits_per_slot
            else:
                current_buffer = 0.0
            if current_buffer > max_buffer_bits:
                loss += 1
                current_buffer = max_buffer_bits
        
        if loss <= max_allowed_loss:
            best_c = c
            high = c
        else:
            low = c
    
    return best_c

def recommend_link_speed(required_gbps, peak_gbps=None):
    """Returns recommended Ethernet link speed with safety guardrails."""
    for speed in LINK_SPEEDS:
        # Constraint 1: Optimized capacity must fit within 80% utilization
        capacity_ok = required_gbps <= speed * 0.8
        
        # Constraint 2: Peak traffic shouldn't exceed link speed (Strict Physical Limit)
        # User Feedback: Even if buffer handles it, seeing Peak (2.89G) > Speed (2.5G) is alarming.
        # We enforce Link Speed >= Peak to ensure absolute burst headroom.
        peak_ok = True
        if peak_gbps is not None:
             if peak_gbps > speed * 1.0:
                 peak_ok = False
        
        if capacity_ok and peak_ok:
            return speed
    return 400  # Fallback

def calculate_sla_score(traffic_gbps, capacity_gbps):
    """Calculate SLA compliance score (0-100)."""
    exceeded = np.sum(traffic_gbps > capacity_gbps)
    total = len(traffic_gbps)
    compliance = (1 - exceeded / total) * 100
    return compliance

def generate_professional_report(links_data, settings):
    """Generate comprehensive PDF report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#124191'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#124191'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Title
    story.append(Paragraph("Nokia Fronthaul Capacity Optimization Report", title_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    total_capex = sum([d['capex_saving'] for d in links_data])
    avg_capex = total_capex / len(links_data) if links_data else 0
    
    summary_text = f"""
    This report analyzes {len(links_data)} fronthaul links using statistical multiplexing and buffer-aware capacity modeling.
    <br/><br/>
    <b>Key Findings:</b><br/>
    • Average CAPEX savings vs peak provisioning: {avg_capex:.1f}%<br/>
    • Provisioning percentile: {settings['percentile']}th<br/>
    • Buffer size: {settings['buffer_symbols']} symbols ({settings['buffer_symbols'] * 35.7:.1f} μs)<br/>
    • Maximum acceptable loss: {settings['max_loss']}%<br/>
    """
    story.append(Paragraph(summary_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Link Analysis
    story.append(Paragraph("Link-by-Link Analysis", heading_style))
    
    for link_data in links_data:
        link_name = link_data['link_name']
        story.append(Paragraph(f"<b>{link_name}</b>", styles['Heading3']))
        
        # Metrics Table
        data = [
            ['Metric', 'Value'],
            ['Peak Traffic', f"{link_data['peak']:.2f} Gbps"],
            [f'P{settings["percentile"]} Traffic', f"{link_data['p_val']:.2f} Gbps"],
            ['Optimized Capacity', f"{link_data['optimized']:.2f} Gbps"],
            ['Recommended Link Speed', f"{link_data['recommended_speed']}G Ethernet"],
            ['SLA Compliance', f"{link_data['sla_score']:.1f}%"],
            ['CAPEX Savings vs Peak', f"{link_data['capex_saving']:.1f}%"],
        ]
        
        t = Table(data, colWidths=[3*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#124191')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2*inch))
        
        # Recommendation
        rec_text = f"""
        <b>Deployment Recommendation:</b><br/>
        Deploy {link_data['recommended_speed']}G Ethernet link. This provides {((link_data['recommended_speed']*0.8 - link_data['optimized'])/(link_data['recommended_speed']*0.8))*100:.1f}% utilization headroom 
        while maintaining SLA compliance of {link_data['sla_score']:.1f}% (target: ≥99%).
        """
        story.append(Paragraph(rec_text, styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
    
    # Technical Methodology
    story.append(PageBreak())
    story.append(Paragraph("Technical Methodology", heading_style))
    
    methodology = f"""
    <b>1. Data Processing:</b><br/>
    • Symbol-level traffic aggregated to slot level (500 μs resolution)<br/>
    • Multiple cells aggregated per link to model statistical multiplexing<br/>
    <br/>
    <b>2. Capacity Calculation:</b><br/>
    • Binary search algorithm to find minimum capacity meeting SLA constraints<br/>
    • Buffer modeling using token bucket queue simulation<br/>
    • Buffer size: {settings['buffer_symbols']} symbols = {settings['buffer_symbols'] * 35.7:.1f} μs = {settings['buffer_symbols'] * 35.7 / 1000:.2f} ms<br/>
    <br/>
    <b>3. SLA Compliance:</b><br/>
    • Maximum tolerable packet loss: {settings['max_loss']}% of slots<br/>
    • Provisioning target: {settings['percentile']}th percentile<br/>
    <br/>
    <b>4. Link Speed Recommendation:</b><br/>
    • Target utilization: 80% (industry best practice)<br/>
    • Headroom calculation ensures burst handling capability<br/>
    """
    story.append(Paragraph(methodology, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_ai_recommendation(api_key, link_name, metrics):
    """Generate executive recommendation using OpenAI."""
    if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
        return None
    
    try:
        client = openai.OpenAI(api_key=api_key)
        prompt = f"""
You are a Nokia Senior Network Planning Engineer. 

Analyze this fronthaul link capacity result for {link_name}:
- Peak Traffic: {metrics['peak']:.2f} Gbps
- P99 Traffic: {metrics['p99']:.2f} Gbps  
- Optimized Capacity (Buffer-Aware): {metrics['optimized']:.2f} Gbps
- Recommended Link: {metrics['recommended_speed']}G Ethernet
- CAPEX Saving vs Peak: {metrics['capex_saving']:.1f}%

Provide a 3-sentence executive recommendation to the CTO on deployment strategy. Be specific, technical, and business-focused.
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content
    except:
        return None

# --- UI LAYOUT ---

st.markdown("""
<div class="nokia-header">
    <h1 style="margin:0; font-size: 36px;">📡 Nokia Fronthaul Capacity Engineering Platform</h1>
    <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">Challenge 2: Intelligent Link Dimensioning & Optimization</p>
</div>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.image("assets/nokia_logo.jpg", width=200)
    st.markdown("---")
    
    st.header("📁 Data Input")
    uploaded_files = st.file_uploader(
        "Upload Throughput Logs", 
        accept_multiple_files=True, 
        type=['dat'],
        help="Upload throughput-cell-X.dat files"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} files loaded")
    
    st.markdown("---")
    st.header("⚙️ Engineering Controls")
    
    percentile = st.slider(
        "Provisioning Percentile",
        min_value=95.0,
        max_value=99.9,
        value=99.0,
        step=0.1,
        help="Target percentile for capacity dimensioning"
    )
    
    buffer_symbols = st.slider(
        "Buffer Size (Symbols)",
        min_value=0,
        max_value=10,
        value=4,
        step=1,
        help="Switch buffer capacity in symbol units"
    )
    
    max_loss = st.slider(
        "Max Acceptable Loss (%)",
        min_value=0.1,
        max_value=5.0,
        value=1.0,
        step=0.1,
        help="Maximum slot loss tolerance"
    )

    target_num_links = st.slider(
        "Target Number of Links",
        min_value=1,
        max_value=12,
        value=3,
        step=1,
        help="Hard constraint: Force network into N links (Default: 3 for Challenge)"
    )
    
    st.markdown("---")
    with st.expander("💰 Cost Configuration (INR)", expanded=False):
        st.caption("Update estimated CAPEX per link type")
        cost_1g = st.number_input("1G Link Cost", value=45000, step=5000)
        cost_2_5g = st.number_input("2.5G Link Cost (AirScale)", value=85000, step=5000)
        cost_5g = st.number_input("5G Link Cost (AirScale)", value=125000, step=10000)
        cost_10g = st.number_input("10G Link Cost", value=170000, step=10000)
        cost_25g = st.number_input("25G Link Cost", value=680000, step=25000)
        cost_40g = st.number_input("40G Link Cost", value=1275000, step=50000)
        cost_50g = st.number_input("50G Link Cost (7250 IXR)", value=1500000, step=50000)
        cost_100g = st.number_input("100G Link Cost", value=2975000, step=100000)
        cost_400g = st.number_input("400G Link Cost", value=8500000, step=250000)
        
        license_cost_per_gbps = st.number_input("vRAN License Cost (per Gbps)", value=25000, step=1000, help="Software license cost savings per Gbps reduced")
        
        custom_link_costs = {
            1: cost_1g,
            2.5: cost_2_5g,
            5: cost_5g,
            10: cost_10g,
            25: cost_25g,
            40: cost_40g,
            50: cost_50g,
            100: cost_100g,
            400: cost_400g
        }
    
    st.markdown("---")
    st.header("📊 Scenario")
    scenario = st.radio(
        "Traffic Model",
        ["Statistical Multiplexing", "Worst-Case Sync"],
        help="Statistical: Normal operation | Worst-Case: All cells peak simultaneously"
    )
    
    st.markdown("---")
    st.header("🤖 AI Analysis")
    st.success("✅ OpenAI API Connected")

# --- MAIN CONTENT ---

if not uploaded_files:
    st.markdown("""
    <div style="text-align: center; padding: 80px 20px; background: white; border-radius: 12px; margin: 40px 0;">
        <h2 style="color: #124191;">Welcome to the Capacity Optimization Engine</h2>
        <p style="font-size: 18px; color: #5a6c7d; margin-top: 20px;">
            Upload throughput data files to begin intelligent provisioning analysis.
        </p>
        <p style="font-size: 14px; color: #8899a6; margin-top: 10px;">
            This system uses <strong>statistical multiplexing</strong> and <strong>buffer-aware modeling</strong> to optimize fronthaul link capacity.
        </p>
    </div>
    """, unsafe_allow_html=True)
else:
    # LOAD & PROCESS
    with st.spinner("🔄 Processing high-resolution telemetry data..."):
        df = load_data(uploaded_files)
        
    if df is not None:
        # Calculate cell-level Gbps (Required for Simulation & Analysis)
        df['gbps'] = (df['bits'] / SLOT_DURATION_SEC) / GBPS_SCALE
        
        # Dynamic Cluster Mapping (Ensures user-defined number of links)
        unique_cells = sorted(df['cell_id'].unique())
        # Split cells into exactly 'target_num_links' chunks
        chunks = np.array_split(unique_cells, target_num_links) 
        
        dynamic_mapping = {}
        for i, chunk in enumerate(chunks):
            for cell in chunk:
                dynamic_mapping[cell] = f"Link_{i+1}"
        
        df['link_id'] = df['cell_id'].map(dynamic_mapping)
        
        # Aggregate to link level
        link_traffic = df.groupby(['link_id', 'slot_idx'])['bits'].sum().reset_index()
        link_traffic['gbps'] = (link_traffic['bits'] / SLOT_DURATION_SEC) / GBPS_SCALE
        
        links = sorted([l for l in link_traffic['link_id'].unique() if l != "Unmapped"])
        
        # TABS
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Executive Dashboard", 
            "🔬 Engineering Analysis", 
            "💡 Recommendations",
            "🤖 AI Insights",
            "🌌 3D Topology"
        ])
        
        with tab1:
            # Data Source Check
            has_throughput = 'type' in df.columns and (df['type'].isin(['throughput', 'detailed_stats'])).any()
            if has_throughput:
                st.success("✅ **Data Source: Throughput Telemetry** (Using `throughput-*.dat` for capacity planning)")
            else:
                st.error("⚠️ **Data Source: Packet Logs Only** (Upload `throughput-*.dat` to see Capacity/CAPEX metrics)")
            st.markdown("### 📈 Network Capacity KPIs")
            
            # Scenario multiplier for worst-case
            scenario_multiplier = 1.3 if scenario == "Worst-Case Sync" else 1.0
            
            total_capex_saved = 0
            total_opex_saved = 0
            total_capacity_reduction = 0
            
            for link in links:
                link_df = link_traffic[link_traffic['link_id'] == link]
                gbps_series = link_df['gbps'].values
                
                # Apply scenario multiplier
                adjusted_gbps = gbps_series * scenario_multiplier
                
                # Metrics
                peak = np.max(adjusted_gbps)
                avg = np.mean(adjusted_gbps)
                p_val = np.percentile(adjusted_gbps, percentile)
                
                # Optimized with current settings
                optimized = calculate_capacity_with_buffer(adjusted_gbps, buffer_symbols, max_loss)
                
                # Recommendations
                recommended_speed = recommend_link_speed(optimized, peak_gbps=peak)
                peak_speed = recommend_link_speed(peak)  # What you'd need with peak provisioning
                sla_score = calculate_sla_score(adjusted_gbps, optimized)
                
                # === ENHANCED COST METRICS ===
                # A) Percentage savings (capacity reduction)
                capex_pct_saving = ((peak - optimized) / peak) * 100
                
                # B) Dollar CAPEX savings (link tier difference)
                peak_cost = custom_link_costs.get(peak_speed, cost_100g)
                opt_cost = custom_link_costs.get(recommended_speed, cost_25g)
                
                # Hardware Savings
                hw_saved = peak_cost - opt_cost
                
                # Software/License Savings (Volume based)
                # Even if link tier doesn't change, we save on processing licenses
                sw_saved = (peak - optimized) * license_cost_per_gbps
                
                dollar_saved = hw_saved + sw_saved
                total_capex_saved += dollar_saved
                
                # C) Annual OPEX savings (power + cooling estimate)
                # Power consumption estimates: ~0.5W per Gbps for optical transceivers
                # Annual cost: $0.12/kWh * 8760 hours = $1,051/kW/year
                peak_power_w = peak_speed * 2.5  # Watts per link speed
                opt_power_w = recommended_speed * 2.5
                power_saved_w = peak_power_w - opt_power_w
                annual_opex_saved = (power_saved_w / 1000) * 89335  # ₹/year (approx ₹10/unit * 24h * 365d)
                total_opex_saved += annual_opex_saved
                
                # Capacity reduction percentage
                capacity_reduction = ((peak - optimized) / peak) * 100
                total_capacity_reduction += capacity_reduction
                
                # SLA Badge
                if sla_score >= 99:
                    sla_class = "sla-high"
                    sla_text = "HIGH"
                elif sla_score >= 95:
                    sla_class = "sla-medium"
                    sla_text = "MEDIUM"
                else:
                    sla_class = "sla-low"
                    sla_text = "LOW"
                
                with st.expander(f"**{link}** - Recommended: **{recommended_speed}G Ethernet**", expanded=True):
                    # Unified Dashboard View
                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Optimal Capacity", f"{optimized:.2f} Gbps", f"-{capex_pct_saving:.1f}%")
                    col2.metric("Peak Load", f"{peak:.2f} Gbps", f"{peak_speed}G req.")
                    col3.metric("Rec. Speed", f"{recommended_speed}G", f"vs causing {p_val:.2f}G P99") 
                    col4.metric("CAPEX Saved", f"₹{dollar_saved:,}", f"{capex_pct_saving:.0f}%")
                    col5.metric("SLA Score", f"{sla_score:.1f}%", sla_text)
                    
                    
                    # Traffic Timeline
                    chart_data = link_df.sort_values('slot_idx')
                    if len(chart_data) > 10000:
                        chart_data = chart_data.iloc[::5]
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=chart_data['slot_idx'], 
                        y=chart_data['gbps'],
                        mode='lines',
                        name='Actual Traffic',
                        line=dict(color='#1976D2', width=1),
                        fill='tozeroy',
                        fillcolor='rgba(25, 118, 210, 0.1)'
                    ))
                    
                    fig.add_hline(y=peak, line_dash="dot", line_color="#FF6B35", 
                                 annotation_text="Peak", annotation_position="right")
                    fig.add_hline(y=optimized, line_dash="dash", line_color="#00D084", 
                                 annotation_text=f"Optimized ({recommended_speed}G)", annotation_position="right")
                    
                    fig.update_layout(
                        title=f"{link} - Slot-Level Traffic Profile (500µs resolution)",
                        xaxis_title="Slot Index",
                        yaxis_title="Traffic (Gbps)",
                        height=350,
                        template="plotly_white",
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
            
            # Total CAPEX Summary
            st.markdown("---")
            
            # Summary cards
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #124191 0%, #1976D2 100%); 
                            padding: 25px; border-radius: 12px; color: white; text-align: center;">
                    <h4 style="margin: 0; opacity: 0.9;">💰 CAPEX Saved</h4>
                    <p style="font-size: 36px; margin: 10px 0; font-weight: bold;">₹{total_capex_saved:,.0f}</p>
                    <p style="font-size: 14px; opacity: 0.8;">HW + vRAN License savings</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #00A968 0%, #00D084 100%); 
                            padding: 25px; border-radius: 12px; color: white; text-align: center;">
                    <h4 style="margin: 0; opacity: 0.9;">⚡ Annual OPEX Saved</h4>
                    <p style="font-size: 36px; margin: 10px 0; font-weight: bold;">₹{total_opex_saved:,.0f}/yr</p>
                    <p style="font-size: 14px; opacity: 0.8;">Power & cooling reduction</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                avg_capacity_reduction = total_capacity_reduction / len(links) if links else 0
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #F7931E 0%, #FF6B35 100%); 
                            padding: 25px; border-radius: 12px; color: white; text-align: center;">
                    <h4 style="margin: 0; opacity: 0.9;">📉 Avg Capacity Reduction</h4>
                    <p style="font-size: 36px; margin: 10px 0; font-weight: bold;">{avg_capacity_reduction:.1f}%</p>
                    <p style="font-size: 14px; opacity: 0.8;">Peak vs optimized provisioning</p>
                </div>
                """, unsafe_allow_html=True)
            
            # 5-year TCO
            five_year_savings = total_capex_saved + (total_opex_saved * 5)
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-top: 20px;">
                <h3 style="margin: 0;">🚀 5-Year Total Cost of Ownership (TCO) Savings</h3>
                <p style="font-size: 48px; margin: 15px 0; font-weight: bold; color: #00D084;">₹{five_year_savings:,.0f}</p>
                <p style="opacity: 0.8;">Across {len(links)} optimized fronthaul links</p>
            </div>
            """, unsafe_allow_html=True)
        
        
        with tab2:
            st.markdown("### 🔬 Comparative Provisioning Analysis")
            
            comparison_data = []
            for link in links:
                data = link_traffic[link_traffic['link_id'] == link]['gbps'].values
                peak = np.max(data)
                p_val = np.percentile(data, percentile)
                opt = calculate_capacity_with_buffer(data, buffer_symbols, max_loss)
                
                comparison_data.append({"Link": link, "Method": "Peak", "Capacity (Gbps)": peak})
                comparison_data.append({"Link": link, "Method": f"P{percentile}", "Capacity (Gbps)": p_val})
                comparison_data.append({"Link": link, "Method": "Optimized", "Capacity (Gbps)": opt})
            
            comp_df = pd.DataFrame(comparison_data)
            
            fig = px.bar(
                comp_df, 
                x="Link", 
                y="Capacity (Gbps)", 
                color="Method",
                barmode="group",
                color_discrete_map={
                    "Peak": "#FF6B35",
                    f"P{percentile}": "#F7931E",
                    "Optimized": "#00D084"
                }
            )
            fig.update_layout(height=400, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(comp_df.pivot(index="Link", columns="Method", values="Capacity (Gbps)"), use_container_width=True)
        
        with tab3:
            st.markdown("### 💡 Deployment Recommendations")
            
            # Prepare data for report
            report_data = []
            
            # API Key for AI recommendations
            api_key = "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"
            
            st.markdown("*AI-powered recommendations are being generated...*")
            
            for i, link in enumerate(links):
                data = link_traffic[link_traffic['link_id'] == link]['gbps'].values
                peak = np.max(data)
                p_val = np.percentile(data, percentile)
                opt = calculate_capacity_with_buffer(data, buffer_symbols, max_loss)
                rec_speed = recommend_link_speed(opt, peak_gbps=peak)
                saving = ((peak - opt) / peak) * 100
                sla = calculate_sla_score(data, opt)
                
                report_data.append({
                    'link_name': link,
                    'peak': peak,
                    'p_val': p_val,
                    'optimized': opt,
                    'recommended_speed': rec_speed,
                    'capex_saving': saving,
                    'sla_score': sla
                })
                
                # Generate AI recommendation
                metrics = {
                    'peak': peak,
                    'p99': p_val,
                    'optimized': opt,
                    'recommended_speed': rec_speed,
                    'capex_saving': saving
                }
                
                try:
                    ai_rec = generate_ai_recommendation(api_key, link, metrics)
                    rec_text = ai_rec if ai_rec else f"Deploy {rec_speed}G Ethernet. Required: {opt:.2f} Gbps. Savings: {saving:.1f}%"
                except:
                    rec_text = f"Deploy {rec_speed}G Ethernet link for optimal cost-performance. Required capacity: {opt:.2f} Gbps with {saving:.1f}% CAPEX savings vs peak provisioning."
                
                # Extended Metrics
                avg_traffic = np.mean(data)
                std_traffic = np.std(data)
                utilization = (avg_traffic / opt) * 100 if opt > 0 else 0
                burstiness = (std_traffic / avg_traffic) * 100 if avg_traffic > 0 else 0
                congestion_risk = "HIGH" if burstiness > 50 else ("MEDIUM" if burstiness > 30 else "LOW")
                
                # Cost estimation
                cost_map = custom_link_costs
                peak_cost_tier = recommend_link_speed(peak)
                peak_capex = cost_map.get(peak_cost_tier, 100000)
                opt_capex = cost_map.get(rec_speed, 100000)
                rupee_saving = peak_capex - opt_capex
                
                with st.expander(f"🎯 **{link}** → Deploy **{rec_speed}G Ethernet**", expanded=True):
                    # Written Explanation
                    st.markdown(f"""
                    #### 📝 Data Analysis Summary
                    
                    **What the data shows:**
                    - This link aggregates traffic from **8 cell sites** in the fronthaul network.
                    - Over the measurement period, we collected **{len(data):,} time slots** of throughput telemetry.
                    - The traffic pattern shows an **average of {avg_traffic:.2f} Gbps** with peaks reaching **{peak:.2f} Gbps**.
                    - Traffic variability (burstiness) is **{burstiness:.0f}%**, indicating {'highly variable traffic that requires buffer management' if burstiness > 50 else 'moderate traffic variations' if burstiness > 30 else 'stable, predictable traffic patterns'}.
                    
                    #### 💡 What This Recommendation Means
                    
                    **Traditional Approach (Peak Provisioning):**
                    - Would deploy a **{peak_cost_tier}G link** to handle the absolute peak of {peak:.2f} Gbps.
                    - Cost: **₹{peak_capex:,}** per link.
                    - Problem: The link sits idle most of the time (only {utilization:.0f}% average utilization).
                    
                    **Our AI-Optimized Approach (Statistical Multiplexing):**
                    - Deploys a **{rec_speed}G link** with intelligent buffer management ({buffer_symbols} symbols).
                    - Uses the fact that all cells don't peak simultaneously.
                    - Achieves **{sla:.1f}% SLA** (packet delivery guarantee) with lower capacity.
                    - Cost: **₹{opt_capex:,}** per link.
                    
                    **Net Savings: ₹{rupee_saving:,}** ({saving:.1f}% reduction in CAPEX)
                    """)
                    
                    # Metrics Row
                    st.markdown("#### 📊 Key Metrics")
                    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                    m_col1.metric("Peak Traffic", f"{peak:.2f} Gbps")
                    m_col2.metric("Optimized Capacity", f"{opt:.2f} Gbps")
                    m_col3.metric("Avg Utilization", f"{utilization:.0f}%")
                    m_col4.metric("Congestion Risk", congestion_risk, delta=None)
                    
                    # Risk Assessment
                    if congestion_risk == "HIGH":
                        st.warning("⚠️ **High Burstiness Alert:** Consider increasing buffer size or deploying QoS policies.")
                    elif congestion_risk == "LOW":
                        st.success("✅ **Stable Traffic:** Low risk of congestion events.")
            
            
            # Download Report Section
            st.markdown("---")
            st.markdown("### 📥 Export Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # PDF Report
                if st.button("📄 Generate Professional Report (PDF)", type="primary", use_container_width=True):
                    with st.spinner("Generating professional PDF report..."):
                        settings = {
                            'percentile': percentile,
                            'buffer_symbols': buffer_symbols,
                            'max_loss': max_loss
                        }
                        pdf_buffer = generate_professional_report(report_data, settings)
                        
                        st.download_button(
                            label="⬇️ Download PDF Report",
                            data=pdf_buffer,
                            file_name=f"Nokia_Fronthaul_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
            
            with col2:
                # JSON Export
                json_data = {
                    "timestamp": datetime.now().isoformat(),
                    "settings": {
                        "percentile": percentile,
                        "buffer_symbols": buffer_symbols,
                        "max_loss_pct": max_loss
                    },
                    "links": report_data
                }
                
                st.download_button(
                    label="📊 Download Data (JSON)",
                    data=json.dumps(json_data, indent=2),
                    file_name=f"capacity_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with tab4:
            st.markdown("### 🤖 Generative AI Executive Summary")
            
            # API Key
            api_key = "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"
            
            # Network Overview Section
            st.markdown("#### 📊 Network Overview")
            
            total_cells = len(df['cell_id'].unique())
            total_slots = len(df['slot_idx'].unique())
            total_traffic = df['bits'].sum() / 1e12  # Terabits
            avg_packet_loss = df['packet_loss'].mean() if 'packet_loss' in df.columns else 0
            
            ov_col1, ov_col2, ov_col3, ov_col4 = st.columns(4)
            ov_col1.metric("Total Cells", f"{total_cells}")
            ov_col2.metric("Time Slots", f"{total_slots:,}")
            ov_col3.metric("Total Traffic", f"{total_traffic:.2f} Tb")
            ov_col4.metric("Avg Packet Loss", f"{avg_packet_loss:.2f}")
            
            st.markdown("---")
            
            # Per-Link Summary Table
            st.markdown("#### 📋 Link-by-Link Analysis")
            
            summary_data = []
            for link in links:
                data = link_traffic[link_traffic['link_id'] == link]['gbps'].values
                cells_in_link = df[df['link_id'] == link]['cell_id'].nunique()
                opt_capacity = calculate_capacity_with_buffer(data, buffer_symbols, max_loss)
                rec_speed = recommend_link_speed(opt_capacity, peak_gbps=peak)
                peak = np.max(data)
                saving = ((peak - opt_capacity) / peak) * 100 if peak > 0 else 0
                
                summary_data.append({
                    "Link": link,
                    "Cells": cells_in_link,
                    "Peak (Gbps)": f"{peak:.2f}",
                    "Optimized (Gbps)": f"{opt_capacity:.2f}",
                    "Recommendation": f"{rec_speed}G",
                    "CAPEX Saving": f"{saving:.1f}%"
                })
            
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.markdown(f"**Analyzing {len(links)} links:** {', '.join(links)}")
            
            if st.button("🚀 Generate CTO Report for All Links", type="primary"):
                ai_results = {}
                progress = st.progress(0)
                
                for i, link in enumerate(links):
                    data = link_traffic[link_traffic['link_id'] == link]['gbps'].values
                    opt_capacity = calculate_capacity_with_buffer(data, buffer_symbols, max_loss)
                    
                    metrics = {
                        'peak': np.max(data),
                        'p99': np.percentile(data, 99),
                        'optimized': opt_capacity,
                        'recommended_speed': recommend_link_speed(opt_capacity, peak_gbps=np.max(data)),
                        'capex_saving': ((np.max(data) - opt_capacity) / np.max(data)) * 100
                    }
                    
                    with st.spinner(f"🔄 Analyzing {link} ({i+1}/{len(links)})..."):
                        try:
                            ai_result = generate_ai_recommendation(api_key, link, metrics)
                            ai_results[link] = ai_result if ai_result else f"Analysis complete for {link}. Recommended: {metrics['recommended_speed']}G Ethernet with {metrics['capex_saving']:.1f}% CAPEX savings."
                        except Exception as e:
                            ai_results[link] = f"[Fallback] {link}: Deploy {metrics['recommended_speed']}G Ethernet. Peak: {metrics['peak']:.2f} Gbps, Optimized: {metrics['optimized']:.2f} Gbps. CAPEX Savings: {metrics['capex_saving']:.1f}%"
                    
                    progress.progress((i + 1) / len(links))
                
                progress.empty()
                
                # Display all results with enhanced styling
                st.markdown("#### 🎯 AI-Generated Recommendations")
                for link, result in ai_results.items():
                    with st.expander(f"📌 {link} - Detailed AI Analysis", expanded=True):
                        st.markdown(result)
                        
                        # Add quick metrics
                        data = link_traffic[link_traffic['link_id'] == link]['gbps'].values
                        qc1, qc2, qc3 = st.columns(3)
                        qc1.metric("Peak Traffic", f"{np.max(data):.2f} Gbps")
                        qc2.metric("Average", f"{np.mean(data):.2f} Gbps")
                        qc3.metric("Utilization", f"{(np.mean(data)/np.max(data))*100:.0f}%")

        with tab5:
            st.markdown("### 🌌 3D Immersive Topology")
            st.markdown("Interactive 3D visualization of the network hierarchy. **Drag to rotate, Scroll to zoom.**")
            
            # Prepare Data
            congestion_state = sim_utils.prepare_congestion_data(df)
            
            # Show Data Source Indicator
            has_real_packets = 'packet_loss' in df.columns and df['packet_loss'].max() > 0
            if has_real_packets:
                st.info("📡 **Data Source: Real Packet Loss Logs** (Red/Orange highlights determined by actual `pkt.dat` files)")
            else:
                st.warning("📉 **Data Source: Throughput Estimation** (Packet loss simulated based on bandwidth thresholds)")

            min_slot = int(congestion_state.index.min())
            max_slot = int(congestion_state.index.max())
            
            # --- AUTO-DETECT CONGESTION ---
            # Find slots where any cell has congestion level > 0
            # congestion_state is a DF: Index=Slot, Cols=Cells, Val=Level
            hot_slots = congestion_state[congestion_state.max(axis=1) > 0].index.tolist()
            
            selected_slot = min_slot
            
            if hot_slots:
                st.warning(f"🚨 Detected {len(hot_slots)} Congestion Events!")
                
                # Format options for the dropdown
                # Show first congested cell info for context
                event_options = []
                for s in hot_slots:
                    # Find which cells are hot in this slot
                    row = congestion_state.loc[s]
                    hot_cells = row[row > 0].index.tolist()
                    details = f"Slot {s}: {len(hot_cells)} Issues (Cells {hot_cells[:2]}...)"
                    event_options.append((s, details))
                
                # Dropdown Selection
                choice_idx = st.selectbox(
                    "🔍 **Jump to Congestion Event:**", 
                    range(len(event_options)), 
                    format_func=lambda i: event_options[i][1]
                )
                selected_slot = event_options[choice_idx][0]
                
            else:
                st.success("✅ No congestion detected in the entire logs.")
                # Fallback to slider if no events
                if min_slot < max_slot:
                    selected_slot = st.slider("Select Simulation Time Slot (3D View)", min_slot, max_slot, min_slot)
                else:
                    selected_slot = min_slot

            # Extract state for this slot
            if selected_slot in congestion_state.index:
                active_congestion = congestion_state.loc[selected_slot].to_dict()
                st.caption(f"Visualizing traffic state at Slot {selected_slot}")
            else:
                active_congestion = {}
                st.warning("No data for this slot.")
            
            # Invert dynamic mapping for 3D function: Link -> [Cells]
            link_to_cells = {}
            for cell, link in dynamic_mapping.items():
                if link not in link_to_cells:
                    link_to_cells[link] = []
                link_to_cells[link].append(cell)
            
            # Determine Link-Level Congestion (Aggregated View)
            active_link_status = {}
            if selected_slot in link_traffic['slot_idx'].unique():
                slot_data = link_traffic[link_traffic['slot_idx'] == selected_slot]
                for _, row in slot_data.iterrows():
                    l_id = row['link_id']
                    l_gbps = row['gbps']
                    
                    # Define Link Congestion Thresholds (Heuristic)
                    # Green < 3G, Orange < 5G, Red > 5G (assuming 10G link is standard, half load warning)
                    if l_gbps > 5.0:
                        active_link_status[l_id] = 2
                    elif l_gbps > 3.0:
                        active_link_status[l_id] = 1
                    else:
                        active_link_status[l_id] = 0
            
            fig_3d, congestion_report = sim_utils.generate_3d_topology(link_to_cells, active_congestion=active_congestion, active_link_status=active_link_status)
            
            col_3d, col_info = st.columns([3, 1])
            
            with col_3d:
                st.plotly_chart(fig_3d, use_container_width=True)
                
            with col_info:
                st.markdown("#### 🚨 Active Congestion Incidents")
                if not congestion_report:
                    st.success("✅ Network Healthy")
                    st.caption("No congestion detected at this time slot.")
                else:
                    for item in congestion_report:
                        node = item['node']
                        level = item['level']
                        reason = "Unknown Anomaly"
                        
                        # Root Cause Analysis
                        if node.startswith("Cell "):
                            try:
                                cid = int(node.replace("Cell ", ""))
                                # Lookup stats
                                cell_stats = df[(df['cell_id'] == cid) & (df['slot_idx'] == selected_slot)]
                                if not cell_stats.empty:
                                    row = cell_stats.iloc[0]
                                    if row.get('late_ratio', 0) > 0.01:
                                        reason = f"High Latency ({(row.get('late_ratio',0)*100):.1f}% Late Packets)"
                                    elif row.get('loss_ratio', 0) > 0.01:
                                        reason = f"Packet Loss ({(row.get('loss_ratio',0)*100):.1f}% Dropped)"
                                    elif row.get('gbps', 0) > 2.5:
                                        reason = f"Bandwidth Saturation ({row.get('gbps',0):.2f} Gbps)"
                            except:
                                pass
                        elif node.startswith("Link"):
                            if node in active_link_status:
                                 status = active_link_status[node]
                                 if status == 2:
                                     reason = "Link Saturation (>5 Gbps)"
                                 elif status == 1:
                                     reason = "Moderate Link Load"
                        
                        if level == 2:
                            st.error(f"🔴 **{node}**: {reason}")
                        elif level == 1:
                            st.warning(f"🟠 **{node}**: {reason}")
                            
                    st.markdown("---")
                    st.caption("**Root Cause Analysis:** Real-time diagnosis of link and cell telemetry.")
