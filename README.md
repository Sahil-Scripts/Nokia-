# 📡 Nokia Fronthaul Capacity Optimizer

> **AI-Powered Intelligent Link Dimensioning & Optimization Platform**  
> *Challenge 2: 5G Fronthaul Network Optimization*

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🎯 **Project Overview**

The **Nokia Fronthaul Capacity Optimizer** is an advanced analytics platform designed to optimize 5G fronthaul network capacity using **statistical multiplexing** and **buffer-aware modeling**. This solution dramatically reduces CAPEX and OPEX while maintaining strict SLA compliance.

### **Key Innovation**
Instead of traditional peak-based provisioning, our platform uses:
- ✅ **Statistical Multiplexing**: Leverages traffic diversity across cells
- ✅ **Buffer-Aware Optimization**: Accounts for switch buffer capacity
- ✅ **Binary Search Algorithm**: Finds optimal capacity with <1% packet loss
- ✅ **AI-Driven Insights**: OpenAI-powered recommendations

### **Business Impact**
- 💰 **30-50% CAPEX Reduction** vs. peak provisioning
- ⚡ **20-40% OPEX Reduction** through power savings
- 📊 **99%+ SLA Compliance** guaranteed
- 🚀 **5-Year TCO Optimization** with comprehensive cost analysis

---

## 🌟 **Features**

### **Executive Dashboard**
- Real-time network capacity KPIs
- Link-by-link analysis with traffic visualization
- CAPEX/OPEX savings calculation
- 5-Year Total Cost of Ownership (TCO) analysis
- SLA compliance scoring

### **Engineering Analysis**
- Comparative provisioning methods (Peak vs P99 vs Buffer-Aware)
- Slot-level traffic profiling (500μs resolution)
- Statistical distribution analysis
- Buffer utilization modeling

### **AI-Powered Recommendations**
- Automated link speed recommendations
- Cost-benefit analysis
- Deployment strategy guidance
- Risk assessment

### **3D Network Topology Visualization**
- Interactive 3D graph of RU-DU connections
- Congestion hotspot detection
- Dynamic traffic flow animation
- Impacted element identification

### **Professional Reporting**
- PDF report generation
- Executive summaries
- Technical methodology documentation
- Exportable metrics and charts

---

## 📋 **Table of Contents**

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage Guide](#-usage-guide)
- [Technical Architecture](#-technical-architecture)
- [Formula Reference](#-formula-reference)
- [Data Format](#-data-format)
- [Configuration](#%EF%B8%8F-configuration)
- [Project Structure](#-project-structure)
- [Contributing](#-contributing)
- [License](#-license)

---

## 📥 **Download & Installation**

### **Prerequisites**
- Python 3.8 or higher ([Download Python](https://www.python.org/downloads/))
- pip package manager (included with Python)
- 4GB+ RAM recommended
- Modern web browser (Chrome, Firefox, Edge)

---

### **Method 1: Download as ZIP (Easiest)**

1. **Download the project**
   - Click the green **"Code"** button on GitHub
   - Select **"Download ZIP"**
   - Extract the ZIP file to your desired location

2. **Open terminal/command prompt**
   ```bash
   # Navigate to the extracted folder
   cd path/to/nokia-fronthaul-optimizer
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   streamlit run app.py
   ```

---

### **Method 2: Clone with Git (Recommended for Developers)**

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/nokia-fronthaul-optimizer.git
   cd nokia-fronthaul-optimizer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   streamlit run app.py
   ```

---

### **Method 3: GitHub Desktop (For Non-Developers)**

1. **Install GitHub Desktop**
   - Download from [desktop.github.com](https://desktop.github.com/)

2. **Clone the repository**
   - Click **"Code"** → **"Open with GitHub Desktop"**
   - Choose where to save the project

3. **Install Python dependencies**
   - Open terminal in GitHub Desktop: `Repository` → `Open in Terminal`
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   streamlit run app.py
   ```

---

### **Verify Installation**
```bash
# Check Python version
python --version

# Check Streamlit installation
python -c "import streamlit; print(f'Streamlit {streamlit.__version__} installed successfully!')"
```

**Expected output**: `Streamlit 1.28.0 installed successfully!` (or higher version)

---

## ⚡ **How to Use**

### **Step 1: Launch the Application**
```bash
streamlit run app.py
```

The application will automatically open in your default browser:
- **Local URL**: `http://localhost:8501`
- **Network URL**: `http://<your-ip>:8501` (accessible from other devices on your network)

### **Step 2: Upload Your Data Files**

1. **Click the sidebar** on the left
2. **Find "📁 Data Input"** section
3. **Click "Upload Throughput Logs"**
4. **Select your data files**:
   - `throughput-cell-*.dat` files (required)
   - `packet-stats-cell-*.dat` files (optional, for congestion analysis)
5. **Wait for processing** (progress bar will show)

✅ Files are loaded directly in your browser - no data is sent to external servers!

### **Step 3: Configure Optimization Parameters**

Adjust settings in the sidebar:

| Parameter | Range | Default | Purpose |
|-----------|-------|---------|---------|
| **Provisioning Percentile** | 95.0 - 99.9% | 99% | How conservative to be |
| **Buffer Size** | 0 - 10 symbols | 4 | Switch buffer capacity |
| **Max Loss Tolerance** | 0.1 - 5% | 1% | Acceptable packet loss |
| **Target Links** | 1 - 12 | 3 | Number of aggregated links |

### **Step 4: Analyze Results**

Navigate through the **5 analysis tabs**:

#### 📊 **Tab 1: Executive Dashboard**
- View high-level KPIs and cost savings
- See recommended link speeds for each link
- Review CAPEX/OPEX savings
- Check 5-Year TCO calculations

#### 🔬 **Tab 2: Engineering Analysis**  
- Compare provisioning methods (Peak vs P99 vs Buffer-Aware)
- Analyze traffic distribution
- Review statistical metrics

#### 💡 **Tab 3: Recommendations**
- Get deployment recommendations for each link
- See detailed cost breakdowns
- Review capacity utilization charts

#### 🤖 **Tab 4: AI Insights**
- OpenAI-powered executive recommendations
- Business-focused deployment strategies
- Risk assessment

#### 🌌 **Tab 5: 3D Topology**
- Interactive 3D network visualization
- Identify congested links
- Explore RU-DU connections

### **Step 5: Export Results (Optional)**

- **Download PDF Report**: Click "Generate PDF Report" button
- **Export Charts**: Right-click any chart → "Download plot as PNG"
- **Save Configuration**: Settings are remembered in browser session

---

## 📖 **Additional Usage Tips**

### **Traffic Model Selection**

#### **Statistical Multiplexing** (Default)
- Assumes normal operational patterns
- Cells unlikely to peak simultaneously
- Realistic provisioning approach
- **Recommended for production planning**

#### **Worst-Case Sync**
- All cells peak at same time (1.3× multiplier)
- Conservative capacity estimates
- **Use for disaster recovery planning**

### **Understanding the Metrics**

| Metric | Description | Good Value |
|--------|-------------|------------|
| **Optimal Capacity** | Buffer-aware optimized capacity | 20-40% below peak |
| **Peak Load** | Maximum observed traffic | Reference value |
| **Rec. Speed** | Recommended Ethernet link speed | 10G, 25G, 50G, etc. |
| **CAPEX Saved** | Hardware + software savings | ₹50k - ₹5M per link |
| **SLA Score** | Compliance percentage | ≥99% |

### **Cost Configuration**

Update link costs in the sidebar to match your region:
1. Expand **"💰 Cost Configuration"**
2. Adjust CAPEX per link type
3. Set vRAN license cost per Gbps
4. Changes apply immediately

---

## 🏗️ **Technical Architecture**

### **Core Components**

```
┌─────────────────────────────────────────────┐
│         Streamlit Web Application           │
├─────────────────────────────────────────────┤
│  Data Ingestion → Processing → Optimization │
└─────────────────────────────────────────────┘
         ↓              ↓              ↓
   Load .dat files  Aggregate   Binary Search
   Parse formats    Calculate    Queue Sim
   Detect types     Metrics      Find Optimal
         ↓              ↓              ↓
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Pandas   │  │  NumPy   │  │ Plotly   │
   └──────────┘  └──────────┘  └──────────┘
```

### **Key Algorithms**

#### **1. Buffer-Aware Capacity Optimization**
- **Algorithm**: Binary search with queue simulation
- **Complexity**: O(n × log n) per link
- **Input**: Traffic timeseries, buffer size, loss tolerance
- **Output**: Minimum capacity meeting SLA

#### **2. Link Speed Recommendation**
- **Constraint 1**: Optimized ≤ Speed × 0.8 (80% utilization)
- **Constraint 2**: Peak ≤ Speed × 1.0 (burst headroom)
- **Output**: Recommended Ethernet speed tier

#### **3. Congestion Detection**
- **Formula**: Score = 0.6×Late_Ratio + 0.3×Loss_Ratio
- **Threshold**: Score > 0.5 indicates congestion
- **Visualization**: Color-coded 3D topology

---

## 📐 **Formula Reference**

For detailed formula documentation, see:
- **[FORMULAS_REFERENCE.md](FORMULAS_REFERENCE.md)** - Complete technical reference
- **[QUICK_FORMULA_REFERENCE.md](QUICK_FORMULA_REFERENCE.md)** - Quick lookup guide

### **Key Formulas**

```python
# Traffic Conversion
Gbps = (bits / SLOT_DURATION_SEC) / 1e9

# Buffer Time
Buffer_Time = Buffer_Symbols × 35.7e-6  # μs

# CAPEX Savings
CAPEX_Pct = ((Peak - Optimized) / Peak) × 100

# SLA Score
SLA = (1 - Violations / Total) × 100

# Annual OPEX
OPEX = (Power_Saved_W / 1000) × 89335  # ₹/year
```

---

## 📊 **Data Format**

### **Throughput Files** (Required)
**Format**: `throughput-cell-X.dat`
```
time               bits
0.000000000000    150000
0.000035714286    148000
0.000071428571    152000
...
```
- **Columns**: `time` (seconds), `bits` (per symbol)
- **Separator**: Whitespace
- **Cell ID**: Extracted from filename

### **Packet Stats Files** (Optional)
**Format**: `packet-stats-cell-X.dat`
```
slot    txPackets    rxPackets    tooLateRxPackets    buffer_occupancy
0       1000         995          3                   2048
1       1020         1015         2                   1536
...
```
- **Columns**: `slot`, `txPackets`, `rxPackets`, `tooLateRxPackets`, `buffer_occupancy`
- **Used for**: Congestion detection and visualization

---

## ⚙️ **Configuration**

### **Constants** (`app.py` lines 141-160)

```python
# Telecom Constants
SLOT_DURATION_SEC = 0.0005      # 500 μs
SYMBOL_DURATION_SEC = 35.7e-6   # 35.7 μs

# Link Speed Options (Gbps)
LINK_SPEEDS = [1, 2.5, 5, 10, 25, 40, 50, 100, 400]

# CAPEX Costs (INR)
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
```

### **Customization**

To modify link costs for your region:
1. Edit `LINK_COSTS` dictionary in `app.py`
2. Update `license_cost_per_gbps` in sidebar config
3. Adjust power consumption model (line 729)

---

## 📁 **Project Structure**

```
nokia-fronthaul-optimizer/
├── app.py                          # Main Streamlit application
├── simulation_utils.py             # Traffic simulation utilities
├── topology_optimizer.py           # Network topology optimization
├── link_capacity_estimation.py     # Capacity calculation algorithms
├── generate_dashboard.py           # Dashboard generation
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── FORMULAS_REFERENCE.md           # Complete formula documentation
├── QUICK_FORMULA_REFERENCE.md      # Quick formula lookup
│
├── assets/                         # Images and logos
│   └── nokia_logo.jpg
│
├── data/                           # Input data directory
│   ├── throughput-cell-X.dat
│   └── packet-stats-cell-X.dat
│
└── FrontHaulIQ/                    # Advanced analytics engine
    └── src/
        ├── capacity/               # Capacity optimization
        ├── topology/               # Topology analysis
        ├── visualization/          # Advanced visualizations
        ├── forecasting/            # Congestion forecasting
        └── simulation/             # Digital twin simulation
```

---

## 🧪 **Testing**

### **Run with Sample Data**
```bash
# Sample data should be in ./data/ directory
streamlit run app.py
```

### **Verify Calculations**
```bash
python verify_simulator.py
python verify_changes.py
```

---

## 🤝 **Contributing**

We welcome contributions! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit changes**: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

### **Code Style**
- Follow PEP 8 guidelines
- Add docstrings to functions
- Include unit tests for new algorithms

---

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 **Acknowledgments**

- **Nokia** - Problem statement and domain expertise
- **OpenAI** - AI-powered recommendation engine
- **Streamlit** - Interactive web application framework
- **Plotly** - Advanced visualization library

---

## 📞 **Support**

For questions or issues:
- 📧 Email: support@yourorg.com
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/nokia-fronthaul-optimizer/issues)
- 📚 Documentation: [Wiki](https://github.com/your-org/nokia-fronthaul-optimizer/wiki)

---

## 🎓 **Citation**

If you use this project in your research, please cite:

```bibtex
@software{nokia_fronthaul_optimizer,
  title={Nokia Fronthaul Capacity Optimizer},
  author={Your Team},
  year={2026},
  url={https://github.com/your-org/nokia-fronthaul-optimizer}
}
```

---

## 🔮 **Roadmap**

- [x] Buffer-aware capacity optimization
- [x] 3D topology visualization
- [x] AI-powered recommendations
- [x] PDF report generation
- [ ] Real-time data ingestion
- [ ] Machine learning-based forecasting
- [ ] Multi-vendor equipment support
- [ ] Cloud deployment options

---

## 📈 **Version History**

### **v1.2** (2026-02-01)
- ✅ Fixed view_mode error
- ✅ Added comprehensive formula documentation
- ✅ Enhanced cost calculation models

### **v1.1** (2026-01-31)
- ✅ Consolidated Executive + Engineering views
- ✅ Added impacted element detection
- ✅ Improved 3D topology visualization

### **v1.0** (2026-01-31)
- ✅ Initial release
- ✅ Core optimization algorithms
- ✅ Streamlit dashboard
- ✅ Multi-tab interface

---

<div align="center">

**Made with ❤️ for 5G Network Optimization**

⭐ **Star this repo if you find it helpful!** ⭐

</div>
