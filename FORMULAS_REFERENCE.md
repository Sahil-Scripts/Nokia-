# Nokia Fronthaul Capacity Optimizer - Calculation Formulas

## 📐 Complete Formula Reference Guide

This document details all mathematical formulas and calculations used in the Nokia Fronthaul Capacity Optimization Platform.

---

## 1️⃣ **Fundamental Constants**

### Telecom Constants
```
SLOT_DURATION_SEC = 0.0005 seconds (500 μs)
SYMBOL_DURATION_SEC = 35.7 × 10⁻⁶ seconds (35.7 μs)
GBPS_SCALE = 10⁹ (1 billion bits)
```

### Link Speed Options (Gbps)
```
Available Speeds = [1, 2.5, 5, 10, 25, 40, 50, 100, 400] Gbps
```

---

## 2️⃣ **Traffic Calculations**

### 2.1 Bits to Gbps Conversion
```
Gbps = (bits / SLOT_DURATION_SEC) / GBPS_SCALE

Where:
- bits = data transmitted in the slot
- SLOT_DURATION_SEC = 0.0005 seconds
- GBPS_SCALE = 10⁹

Example:
If bits = 250,000
Gbps = (250,000 / 0.0005) / 10⁹
     = 500,000,000 / 10⁹
     = 0.5 Gbps
```

### 2.2 Slot Index Calculation
```
slot_idx = (time - min_time) / SLOT_DURATION_SEC

Where:
- time = current timestamp
- min_time = minimum timestamp in dataset
- Result is converted to integer
```

### 2.3 Link Level Aggregation
```
Link_Traffic[slot_idx] = Σ(Cell_i_Traffic[slot_idx])

Where the sum is over all cells assigned to that link.
```

### 2.4 Scenario Multiplier (Worst-Case Analysis)
```
Adjusted_Traffic = Traffic × Scenario_Multiplier

Where:
- Scenario_Multiplier = 1.3 (for Worst-Case Sync)
- Scenario_Multiplier = 1.0 (for Statistical Multiplexing)
```

---

## 3️⃣ **Statistical Metrics**

### 3.1 Peak Traffic
```
Peak = max(Traffic_Gbps)

Maximum value across all time slots
```

### 3.2 Average Traffic
```
Average = mean(Traffic_Gbps) = Σ(Traffic_i) / N

Where N = total number of slots
```

### 3.3 Percentile Traffic (P99, P95, etc.)
```
P_val = percentile(Traffic_Gbps, percentile)

Where:
- percentile = user-defined value (e.g., 99.0 for P99)
- Uses NumPy's percentile function
```

---

## 4️⃣ **Buffer-Aware Capacity Optimization**

### 4.1 Buffer Time Calculation
```
Buffer_Time_Sec = Buffer_Symbols × SYMBOL_DURATION_SEC

Where:
- Buffer_Symbols = user-defined (default: 4)
- SYMBOL_DURATION_SEC = 35.7 × 10⁻⁶ seconds

Example:
Buffer_Time_Sec = 4 × 35.7 × 10⁻⁶ = 142.8 μs
```

### 4.2 Optimized Capacity (Binary Search Algorithm)

**Purpose:** Find minimum capacity that satisfies SLA constraints

```
Initialize:
    Low = mean(Traffic_Gbps)
    High = max(Traffic_Gbps)
    Traffic_Bits[i] = Traffic_Gbps[i] × GBPS_SCALE × SLOT_DURATION_SEC
    Max_Allowed_Loss = Total_Slots × (Max_Loss_Pct / 100)

Binary Search (15 iterations):
    For each iteration:
        Candidate_Capacity = (Low + High) / 2
        
        Capacity_Bits_Per_Slot = Candidate_Capacity × GBPS_SCALE × SLOT_DURATION_SEC
        Max_Buffer_Bits = Buffer_Time_Sec × (Candidate_Capacity × GBPS_SCALE)
        
        Simulate Queue:
            Current_Buffer = 0
            Loss_Count = 0
            
            For each slot:
                Current_Buffer += Traffic_Bits[slot]
                
                If Current_Buffer > Capacity_Bits_Per_Slot:
                    Current_Buffer -= Capacity_Bits_Per_Slot
                Else:
                    Current_Buffer = 0
                
                If Current_Buffer > Max_Buffer_Bits:
                    Loss_Count += 1
                    Current_Buffer = Max_Buffer_Bits
            
        If Loss_Count <= Max_Allowed_Loss:
            Best_Capacity = Candidate_Capacity
            High = Candidate_Capacity  // Search lower
        Else:
            Low = Candidate_Capacity   // Search higher

Return Best_Capacity
```

**Key Formulas:**
```
Capacity_Bits_Per_Slot = C × 10⁹ × 0.0005
Max_Buffer_Bits = Buffer_Time_Sec × C × 10⁹
Max_Allowed_Loss = Total_Slots × (Max_Loss_Pct / 100)
```

---

## 5️⃣ **Link Speed Recommendation**

### 5.1 Link Speed Selection Logic
```
For each available speed in [1, 2.5, 5, 10, 25, 40, 50, 100, 400]:
    
    Constraint 1: Utilization Check (80% rule)
        Capacity_OK = (Required_Gbps <= Speed × 0.8)
    
    Constraint 2: Peak Burst Headroom
        Peak_OK = (Peak_Gbps <= Speed × 1.0)
    
    If (Capacity_OK AND Peak_OK):
        Return Speed
    
Fallback: Return 400 Gbps
```

**Formulas:**
```
Target_Utilization_Threshold = Speed × 0.8
Peak_Headroom_Threshold = Speed × 1.0
```

---

## 6️⃣ **SLA Compliance Score**

### 6.1 SLA Score Calculation
```
Exceeded_Slots = count(Traffic_Gbps > Capacity_Gbps)
Total_Slots = length(Traffic_Gbps)

SLA_Compliance = (1 - Exceeded_Slots / Total_Slots) × 100

Range: 0% to 100%
```

**Interpretation:**
- ≥99%: HIGH (Green)
- ≥95%: MEDIUM (Orange)
- <95%: LOW (Red)

---

## 7️⃣ **Cost Calculations**

### 7.1 CAPEX Percentage Saving
```
CAPEX_Pct_Saving = ((Peak - Optimized) / Peak) × 100

Where:
- Peak = peak traffic in Gbps
- Optimized = buffer-aware optimized capacity in Gbps
```

### 7.2 Hardware CAPEX Savings (₹)
```
Peak_Cost = LINK_COSTS[Peak_Speed]
Optimized_Cost = LINK_COSTS[Recommended_Speed]

HW_Saved = Peak_Cost - Optimized_Cost

Where LINK_COSTS in INR:
    1G    → ₹45,000
    2.5G  → ₹85,000
    5G    → ₹125,000
    10G   → ₹170,000
    25G   → ₹680,000
    40G   → ₹1,275,000
    50G   → ₹1,500,000
    100G  → ₹2,975,000
    400G  → ₹8,500,000
```

### 7.3 Software/License Savings (₹)
```
SW_Saved = (Peak - Optimized) × License_Cost_Per_Gbps

Where:
- License_Cost_Per_Gbps = ₹25,000 (default)
- (Peak - Optimized) = capacity reduction in Gbps
```

### 7.4 Total CAPEX Savings (₹)
```
Total_CAPEX_Saved = HW_Saved + SW_Saved
```

### 7.5 Annual OPEX Savings (₹)

**Power Consumption Model:**
```
Peak_Power_W = Peak_Speed × 2.5  // Watts
Optimized_Power_W = Recommended_Speed × 2.5  // Watts
Power_Saved_W = Peak_Power_W - Optimized_Power_W

Annual_OPEX_Saved = (Power_Saved_W / 1000) × 89,335

Where:
- 2.5W per Gbps = power consumption estimate
- 89,335 = ₹10/unit × 24 hours × 365 days × 1.02 (cooling overhead)
```

### 7.6 Capacity Reduction Percentage
```
Capacity_Reduction = ((Peak - Optimized) / Peak) × 100
```

### 7.7 Five-Year TCO Savings
```
Five_Year_TCO_Savings = Total_CAPEX_Saved + (Annual_OPEX_Saved × 5)
```

---

## 8️⃣ **Congestion Detection**

### 8.1 Late Packet Ratio
```
Late_Ratio = Too_Late_Rx_Packets / Rx_Packets

Note: Division by zero avoided by replacing 0 with 1
```

### 8.2 Packet Loss Ratio
```
Loss_Ratio = (Tx_Packets - Rx_Packets) / Tx_Packets
Loss_Ratio = max(0, Loss_Ratio)  // Clipped to non-negative
```

### 8.3 Congestion Score (Weighted)
```
Congestion_Score = 0.6 × Late_Ratio + 0.3 × Loss_Ratio

Weights:
- Late packets: 60% (high impact on latency)
- Packet loss: 30% (moderate impact)
- Total: 90% (10% reserved for optional load factor)

Range: 0.0 to 1.0
```

### 8.4 Binary Congestion (Fallback)
```
Congestion_Score = 0.5 × (Packet_Loss > 0 ? 1 : 0)

Result: 0.0 (no congestion) or 0.5 (congestion detected)
```

---

## 9️⃣ **Packet Delta Calculation**

### 9.1 Cumulative Counter Detection
```
Is_Cumulative = all(Rx_Packets[i] <= Rx_Packets[i+1]) for all i

If cumulative counters detected:
    Delta[i] = Current[i] - Previous[i]
    Delta[0] = Current[0]  // Backfilled
```

### 9.2 Estimated Bits from Packets
```
Estimated_Bits = Rx_Packets × 8 × 1500

Where:
- 8 = bits per byte
- 1500 = assumed MTU (Maximum Transmission Unit) in bytes
```

---

## 🔟 **Topology Optimization**

### 10.1 Cell-to-Link Mapping
```
Dynamic_Mapping:
    Unique_Cells = sorted(unique cell IDs)
    Chunks = array_split(Unique_Cells, Target_Num_Links)
    
    For i, chunk in enumerate(Chunks):
        For cell in chunk:
            Mapping[cell] = f"Link_{i+1}"
```

---

## 📊 **Summary Metrics**

### Average CAPEX Savings Across Links
```
Avg_CAPEX_Saving = Total_CAPEX_Saved / Num_Links
```

### Average Capacity Reduction
```
Avg_Capacity_Reduction = Total_Capacity_Reduction / Num_Links

Where:
Total_Capacity_Reduction = Σ(Capacity_Reduction_i) for all links
```

---

## 📝 **Example Calculation Walkthrough**

### Given:
- Peak Traffic = 10 Gbps
- Optimized Capacity = 6.5 Gbps (from buffer-aware algorithm)
- Buffer Symbols = 4
- Max Loss = 1%
- License Cost = ₹25,000/Gbps

### Step-by-Step:

**1. Buffer Time:**
```
Buffer_Time = 4 × 35.7 × 10⁻⁶ = 142.8 μs
```

**2. Link Speed Recommendation:**
```
For 10G: 6.5 <= 10 × 0.8 = 8 ✓ AND 10 <= 10 × 1.0 ✓
Recommended_Speed = 10 Gbps
```

**3. CAPEX Percentage Saving:**
```
CAPEX_Pct = (10 - 6.5) / 10 × 100 = 35%
```

**4. Hardware Savings:**
```
Peak needs 10G → ₹170,000
Optimized needs 10G → ₹170,000
HW_Saved = ₹0 (same tier)
```

**5. Software Savings:**
```
SW_Saved = (10 - 6.5) × 25,000 = ₹87,500
```

**6. Total CAPEX:**
```
Total_CAPEX = ₹0 + ₹87,500 = ₹87,500
```

**7. Power Savings:**
```
Peak_Power = 10 × 2.5 = 25W
Opt_Power = 10 × 2.5 = 25W
Power_Saved = 0W
Annual_OPEX = ₹0
```

**8. Five-Year TCO:**
```
TCO = ₹87,500 + (₹0 × 5) = ₹87,500
```

---

## 🎯 **Key Optimization Guidelines**

1. **80% Utilization Rule**: Keep link utilization ≤80% for headroom
2. **P99 Provisioning**: Provision for 99th percentile, not peak
3. **Buffer Benefits**: 4-symbol buffer reduces capacity ~15-30%
4. **SLA Target**: Maintain ≥99% compliance
5. **TCO Focus**: Consider 5-year total cost, not just CAPEX

---

**Generated by Nokia Fronthaul Capacity Optimizer**  
**Version 1.0 | Challenge 2 | 5G Fronthaul Network Optimization**
