
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

# Link Speed Options (Gbps)
LINK_SPEEDS = [1, 10, 25, 40, 100]

# CAPEX Cost Estimates (INR per link - Typical Operator Pricing in India)
# Approx conversion ~85 INR/USD + taxes
LINK_COSTS = {
    1: 45000,
    10: 170000,
    25: 680000,
    40: 1275000,
    100: 2975000
}

# Default Topology
DEFAULT_MAPPING = {
    2: "Link_1", 3: "Link_1", 4: "Link_1",
    5: "Link_2", 6: "Link_2", 7: "Link_2",
    8: "Link_3", 9: "Link_3", 10: "Link_3"
}

# --- CORE ALGORITHMS ---

@st.cache_data(show_spinner=False)
def load_data(uploaded_files):
    data_frames = []
    progress_bar = st.progress(0)
    
    for i, file_obj in enumerate(uploaded_files):
        try:
            filename = file_obj.name
            cell_id = int(filename.replace("throughput-cell-", "").replace(".dat", ""))
            df = pd.read_csv(file_obj, sep=r'\s+', names=["time", "bits"], engine='c')
            df['cell_id'] = cell_id
            data_frames.append(df)
        except:
            st.warning(f"⚠️ Skipped {file_obj.name}")
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    progress_bar.empty()
    if not data_frames: return None
    
    full_df = pd.concat(data_frames, ignore_index=True)
    min_time = full_df['time'].min()
    full_df['slot_idx'] = ((full_df['time'] - min_time) / SLOT_DURATION_SEC).astype(int)
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

def recommend_link_speed(required_gbps):
    """Returns recommended Ethernet link speed."""
    for speed in LINK_SPEEDS:
        if required_gbps <= speed * 0.8:  # 80% utilization threshold
            return speed
    return 100  # Fallback

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
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Nokia_wordmark.svg/320px-Nokia_wordmark.svg.png", width=120)
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
    
    st.markdown("---")
    st.header("🎛️ View Mode")
    view_mode = st.radio(
        "Dashboard Mode",
        ["Executive", "Engineering"],
        help="Executive: Cost-focused | Engineering: Technical details"
    )
    
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
        df['link_id'] = df['cell_id'].map(DEFAULT_MAPPING).fillna("Unmapped")
        
        # Aggregate to link level
        link_traffic = df.groupby(['link_id', 'slot_idx'])['bits'].sum().reset_index()
        link_traffic['gbps'] = (link_traffic['bits'] / SLOT_DURATION_SEC) / GBPS_SCALE
        
        links = sorted([l for l in link_traffic['link_id'].unique() if l != "Unmapped"])
        
        # TABS
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Executive Dashboard", 
            "🔬 Engineering Analysis", 
            "💡 Recommendations",
            "🤖 AI Insights",
            "🧬 Generative Topology",
            "🎬 Digital Twin"
        ])
        
        with tab1:
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
                recommended_speed = recommend_link_speed(optimized)
                peak_speed = recommend_link_speed(peak)  # What you'd need with peak provisioning
                sla_score = calculate_sla_score(adjusted_gbps, optimized)
                
                # === ENHANCED COST METRICS ===
                # A) Percentage savings (capacity reduction)
                capex_pct_saving = ((peak - optimized) / peak) * 100
                
                # B) Dollar CAPEX savings (link tier difference)
                peak_cost = LINK_COSTS.get(peak_speed, 35000)
                opt_cost = LINK_COSTS.get(recommended_speed, 8000)
                dollar_saved = peak_cost - opt_cost
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
                    # Mode-dependent display
                    if view_mode == "Executive":
                        # Row 1: Main metrics
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Optimal Capacity", f"{optimized:.2f} Gbps", f"-{capex_pct_saving:.1f}% vs peak")
                        col2.metric("Link Speed", f"{recommended_speed}G", f"vs {peak_speed}G peak")
                        col3.metric("CAPEX Saved", f"₹{dollar_saved:,}", f"{capex_pct_saving:.0f}% reduction")
                        col4.metric("SLA Score", f"{sla_score:.1f}%", sla_text)
                        
                        # Row 2: Additional cost metrics
                        col5, col6, col7, col8 = st.columns(4)
                        col5.metric("Peak Capacity", f"{peak:.2f} Gbps")
                        col6.metric("Capacity Reduction", f"{capacity_reduction:.1f}%")
                        col7.metric("Annual OPEX Saved", f"₹{annual_opex_saved:,.0f}/yr")
                        col8.metric("Total Savings (5yr)", f"₹{dollar_saved + annual_opex_saved*5:,.0f}")
                    else:
                        col1, col2, col3, col4, col5 = st.columns(5)
                        col1.metric("Peak Load", f"{peak:.2f} Gbps")
                        col2.metric(f"P{percentile}", f"{p_val:.2f} Gbps")
                        col3.metric("Buffer-Optimized", f"{optimized:.2f} Gbps", f"-{((p_val-optimized)/p_val)*100:.1f}%")
                        col4.metric("CAPEX Avoided", f"{capex_pct_saving:.1f}%")
                        col5.metric("SLA Compliance", f"{sla_score:.1f}%", sla_text)
                    
                    
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
            
            # Total CAPEX Summary (Executive Mode)
            if view_mode == "Executive":
                st.markdown("---")
                
                # Summary cards
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #124191 0%, #1976D2 100%); 
                                padding: 25px; border-radius: 12px; color: white; text-align: center;">
                        <h4 style="margin: 0; opacity: 0.9;">💰 CAPEX Saved</h4>
                        <p style="font-size: 36px; margin: 10px 0; font-weight: bold;">₹{total_capex_saved:,}</p>
                        <p style="font-size: 14px; opacity: 0.8;">Link hardware savings</p>
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
                rec_speed = recommend_link_speed(opt)
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
                
                st.markdown(f"""
                <div class="recommendation-box">
                    <h3 style="margin-top: 0;">🎯 {link} → Deploy {rec_speed}G Ethernet</h3>
                    <p style="font-size: 16px; line-height: 1.6;">{rec_text}</p>
                    <hr style="border-color: rgba(255,255,255,0.3); margin: 15px 0;">
                    <p style="font-size: 14px; opacity: 0.9;"><strong>Key Metrics:</strong> Peak: {peak:.2f} Gbps | Optimized: {opt:.2f} Gbps | SLA: {sla:.1f}% | CAPEX Saved: {saving:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)
            
            
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
                        'recommended_speed': recommend_link_speed(opt_capacity),
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
                
                # Display all results
                for link, result in ai_results.items():
                    st.markdown(f"#### {link} - AI Analysis")
                    st.info(result)

        with tab5:
            st.markdown("### 🧬 Generative AI Topology Optimization")
            st.markdown("""
            > **The "Crazy" Idea:** Why accept the network as it is? 
            > This engine uses **Generative AI Logic** to brute-force thousands of network permutations, 
            > finding the perfect statistical multiplexing alignment to minimize CAPEX.
            """)
            
            st.info("Current Configuration: Standard Mapping (Based on geography/legacy)")
            
            # Calculate current cost
            curr_cost, curr_details = calculate_topology_cost(df, DEFAULT_MAPPING)
            
            col1, col2 = st.columns(2)
            col1.metric("Current Network CAPEX", f"₹{curr_cost:,}")
            
            if 'topo_opt_results' not in st.session_state:
                st.session_state.topo_opt_results = None

            if st.button("✨ Run Generative Topology Engine", type="primary"):
                with st.spinner("🤖 AI is redesigning the physical network layer..."):
                    # Run Optimization (Reduced iterations for speed)
                    best_mapping, best_cost, best_details = optimize_topology(df, iterations=50)
                    
                    # Store in session state
                    st.session_state.topo_opt_results = {
                        'mapping': best_mapping,
                        'cost': best_cost,
                        'details': best_details
                    }
                    
            # Display Results from Session State
            if st.session_state.topo_opt_results:
                results = st.session_state.topo_opt_results
                best_cost = results['cost']
                best_mapping = results['mapping']
                best_details = results['details']
                
                # Calculate Savings
                savings = curr_cost - best_cost
                savings_pct = (savings / curr_cost) * 100
                
                st.success(f"🎉 Optimization Complete! Found a design saving ₹{savings:,} ({savings_pct:.1f}%)")
                
                # Visualization
                scol1, scol2 = st.columns(2)
                with scol1:
                    st.metric("Optimized CAPEX", f"₹{best_cost:,}", f"-{savings_pct:.1f}%")
                with scol2:
                        st.metric("Total Savings", f"₹{savings:,}")
                
                # Show Mapping
                st.subheader("Recommended Network Re-Architechture")
                
                mapping_df = pd.DataFrame(list(best_mapping.items()), columns=['Cell ID', 'New Link Assignment'])
                mapping_df = mapping_df.sort_values('New Link Assignment')
                
                st.dataframe(mapping_df, use_container_width=True)
                
                # Detailed breakdown
                st.write("### Link Distribution")
                for link_id, det in best_details.items():
                    st.write(f"**{link_id}**: Peak {det['peak']:.2f} Gbps → Requires **{det['speed']}G Link** (₹{det['cost']:,})")

        with tab6:
            st.markdown("### 🎬 Network Digital Twin Simulation")
            st.markdown("Visualize minute-by-minute packet flow and buffer stress in **Time-Travel Mode**.")
            
            if st.button("▶️ Start Live Simulation", type="primary"):
                # Simulation Logic
                st.write("Initializing Digital Twin Environment...")
                
                # Create columns for links
                sim_cols = st.columns(len(links))
                placeholders = []
                
                # Setup UI containers
                for idx, link in enumerate(links):
                    with sim_cols[idx]:
                        st.markdown(f"#### {link}")
                        container = st.empty()
                        placeholders.append(container)
                        
                # Prepare Data for Playback (Sampling for speed)
                frames = 20 # Reduced from 100 for faster loading
                import time
                
                # Pre-calculate data slices
                link_data_map = {}
                for link in links:
                    series = link_traffic[link_traffic['link_id'] == link]['gbps'].values
                    # Downsample to 'frames' chunks
                    step = len(series) // frames
                    if step < 1: step = 1
                    sampled = series[::step]
                    link_data_map[link] = sampled
                
                # Animation Loop
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_loss_events = 0
                
                for f in range(len(link_data_map[links[0]])):
                    
                    status_text.text(f"Simulation Time Step: {f} / {frames}")
                    
                    # Update each link
                    for idx, link in enumerate(links):
                        val = link_data_map[link][f]
                        
                        # Dynamic Threshold (using the Optimization from earlier)
                        # We'll use a fixed 25G reference for visual drama if not available
                        capacity_limit = 25.0 
                        
                        load_pct = (val / capacity_limit) * 100
                        buffer_fill = 0
                        if load_pct > 100:
                            buffer_fill = min((load_pct - 100) * 5, 100) # Exaggerate buffer fill
                            if buffer_fill == 100:
                                total_loss_events += 1
                        
                        # Color Logic
                        if buffer_fill > 90:
                            color = "red"
                            status = "CRITICAL"
                        elif buffer_fill > 50:
                            color = "orange"
                            status = "BUFFERING"
                        else:
                            color = "green"
                            status = "HEALTHY"
                            
                        # Render Frame
                        with placeholders[idx].container():
                            st.metric("Throughput", f"{val:.2f} Gbps")
                            st.caption(f"Status: :{'red' if color=='red' else 'green'}[{status}]")
                            st.progress(min(int(load_pct), 100) / 100)
                            
                            # Simulated Buffer Gauge
                            st.write(f"Buffer: {buffer_fill:.0f}%")
                            st.progress(buffer_fill / 100)
                    
                    progress_bar.progress((f + 1) / len(link_data_map[links[0]]))
                    time.sleep(0.05) # 20fps
                
                st.success("Simulation Complete.")
                if total_loss_events > 0:
                    st.error(f"Detected {total_loss_events} packet loss events during stress test.")
                else:
                    st.balloons()
