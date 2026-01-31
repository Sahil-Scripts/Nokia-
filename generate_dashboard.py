
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# Configuration
DATA_DIR = "s:/fronthaul_ai/data"
JSON_FILE = "s:/fronthaul_ai/results_final.json"
CSV_FILE = os.path.join(DATA_DIR, "link_traffic_timeseries.csv")
OUTPUT_HTML = "s:/fronthaul_ai/ch2_dashboard.html"

def load_data():
    # Load JSON results (parsing tricky due to stdout noise in file, so we re-run logic or clean file)
    # Actually, the file contains stdout noise. Let's rely on the CSV for the graphs
    # and maybe hardcode or re-calc the summary if the JSON is dirty.
    # PRO TRICK: Robust JSON loader using a regex to find the last valid JSON object brace
    # But since we generated it, let's just use the python script logic again or assume we can parse it.
    
    # Let's try to parse the last valid JSON from the results file
    # The 'type' output showed noise at start.
    
    with open(JSON_FILE, 'r') as f:
        results = json.load(f)
            
    # Load CSV
    df = pd.read_csv(CSV_FILE)
    return results, df

def create_dashboard():
    results, df = load_data()
    
    # Initialize Dashboard
    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=("Link Traffic Overview (Gbps per Slot)", "Peak vs P99 vs Buffer-Aware Capacity", "Optimization Impact"),
        vertical_spacing=0.1,
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}], [{"type": "domain"}]] # Adjust specs if needed
    )
    
    # SECTION 2: Slot-Level Traffic Graph (Time Series)
    # Sampling for performance (plot every 10th point if huge)
    # df is likely large (~1M points). Plotly handles ~100k well.
    # Let's aggregate slightly for view or plot a slice.
    
    colors = {"Link_1": "purple", "Link_2": "blue", "Link_3": "cyan"}
    
    for link in df['link_id'].unique():
        link_df = df[df['link_id'] == link].sort_values('slot_idx')
        # Limit points
        if len(link_df) > 10000:
            link_df = link_df.iloc[::10] 
            
        fig.add_trace(
            go.Scatter(x=link_df['slot_idx'], y=link_df['gbps'], mode='lines', name=f"{link} Traffic", line=dict(width=1), opacity=0.7),
            row=1, col=1
        )
        
        # Add Lines for Limits (P99, Peak) if available
        if results and "link_results" in results:
            res = results["link_results"].get(link)
            if res:
                fig.add_hline(y=res['required_99_percentile_gbps'], line_dash="dash", line_color="orange", annotation_text=f"{link} P99", row=1, col=1)
                fig.add_hline(y=res['required_with_buffer_gbps'], line_dash="dot", line_color="green", annotation_text=f"{link} Buffer", row=1, col=1)

    # SECTION 3: Peak vs Percentile Comparison (Bar Chart)
    if results and "link_results" in results:
        links = []
        peak_vals = []
        p99_vals = []
        buffer_vals = []
        
        for k, v in results["link_results"].items():
            links.append(k)
            peak_vals.append(v['peak_gbps'])
            p99_vals.append(v['required_99_percentile_gbps'])
            buffer_vals.append(v['required_with_buffer_gbps'])
            
        fig.add_trace(go.Bar(name='Peak Provisioning', x=links, y=peak_vals, marker_color='red'), row=2, col=1)
        fig.add_trace(go.Bar(name='P99 Provisioning', x=links, y=p99_vals, marker_color='orange'), row=2, col=1)
        fig.add_trace(go.Bar(name='Buffer-Aware (Optimal)', x=links, y=buffer_vals, marker_color='green'), row=2, col=1)

    # SECTION 1: Summary Table
    if results and "link_results" in results:
        header = ["Link", "Avg Gbps", "Peak Gbps", "P99 Gbps", "Buffer Gbps", "Overprovision Avoided %"]
        cells = []
        for k, v in results["link_results"].items():
            cells.append([
                k, v['average_gbps'], v['peak_gbps'], v['required_99_percentile_gbps'], 
                v['required_with_buffer_gbps'], v['overprovision_if_peak_based_percent']
            ])
        
        # Transpose for plotly table
        cell_data = list(map(list, zip(*cells)))
        
        fig.add_trace(
            go.Table(
                header=dict(values=header, fill_color='paleturquoise', align='left'),
                cells=dict(values=cell_data, fill_color='lavender', align='left')
            ),
            row=3, col=1
        )

    # Layout Updates
    fig.update_layout(
        title_text="<b>Nokia Fronthaul Link Capacity Optimization - Challenge 2</b>",
        height=1200,
        template="plotly_white",
        showlegend=True
    )
    
    # Explanation
    explanation = results.get("telecom_explanation", "Analysis complete.") if results else ""
    
    # Save
    fig.write_html(OUTPUT_HTML)
    print(f"Dashboard saved to {OUTPUT_HTML}")

if __name__ == "__main__":
    create_dashboard()
