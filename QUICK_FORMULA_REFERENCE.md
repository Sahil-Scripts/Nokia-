# Quick Formula Reference - Nokia Fronthaul Optimizer

## 📋 **Quick Lookup Table**

| Category | Formula | Variables | Example |
|----------|---------|-----------|---------|
| **Traffic Conversion** | `Gbps = bits / (0.0005 × 10⁹)` | bits = data per slot | 250k bits → 0.5 Gbps |
| **Buffer Time** | `Buffer_Time = Symbols × 35.7μs` | Symbols = buffer size | 4 symbols → 142.8μs |
| **Peak Traffic** | `Peak = max(Traffic)` | - | - |
| **Average Traffic** | `Avg = Σ(Traffic) / N` | N = number of slots | - |
| **Percentile** | `P99 = percentile(Traffic, 99)` | - | - |
| **CAPEX Savings %** | `Savings = (Peak - Opt) / Peak × 100` | Opt = optimized capacity | (10-6.5)/10 = 35% |
| **HW Savings ₹** | `HW = Peak_Cost - Opt_Cost` | From LINK_COSTS table | ₹170k - ₹125k = ₹45k |
| **SW Savings ₹** | `SW = (Peak - Opt) × 25000` | ₹25k per Gbps | 3.5 × 25k = ₹87.5k |
| **Total CAPEX ₹** | `CAPEX = HW + SW` | - | ₹45k + ₹87.5k = ₹132.5k |
| **Power (Watts)** | `Power = Speed × 2.5` | Speed in Gbps | 10G → 25 Watts |
| **Annual OPEX ₹** | `OPEX = (Power_Saved/1000) × 89335` | Power in Watts | 25W → ₹2,233/year |
| **5-Year TCO ₹** | `TCO = CAPEX + (OPEX × 5)` | - | ₹132.5k + (₹2.2k × 5) |
| **SLA Score** | `SLA = (1 - Exceeded/Total) × 100` | Exceeded = violations | (1 - 50/10000) × 100 = 99.5% |
| **Link Selection** | `Req ≤ Speed × 0.8 AND Peak ≤ Speed` | 80% utilization rule | 6.5 ≤ 10×0.8 ✓ |
| **Congestion** | `Score = 0.6×Late + 0.3×Loss` | Ratios from 0-1 | 0.02 late + 0.01 loss = 0.015 |

---

## 🎯 **Common Calculations**

### 1. Convert Traffic to Gbps
```python
Gbps = (bits / SLOT_DURATION_SEC) / GBPS_SCALE
     = (bits / 0.0005) / 1,000,000,000
```

### 2. Find Optimized Capacity
```python
# Binary search between mean and peak
Low = mean(Traffic)
High = max(Traffic)
# Iterate to find minimum capacity meeting <1% loss
```

### 3. Calculate Total CAPEX Savings
```python
HW_Savings = LINK_COSTS[peak_speed] - LINK_COSTS[opt_speed]
SW_Savings = (peak_gbps - opt_gbps) × 25000
Total_CAPEX = HW_Savings + SW_Savings
```

### 4. Calculate Annual OPEX Savings
```python
Peak_Power_W = peak_speed × 2.5
Opt_Power_W = opt_speed × 2.5
Power_Saved = Peak_Power_W - Opt_Power_W
Annual_OPEX = (Power_Saved / 1000) × 89335  # ₹/year
```

### 5. Determine Link Speed
```python
for speed in [1, 2.5, 5, 10, 25, 40, 50, 100, 400]:
    if (optimized ≤ speed × 0.8) AND (peak ≤ speed):
        return speed
```

---

## 💰 **Link Costs (INR)**

| Speed | CAPEX (₹) | Power (W) | Annual Power Cost (₹) |
|-------|-----------|-----------|----------------------|
| 1G | 45,000 | 2.5 | 223 |
| 2.5G | 85,000 | 6.25 | 558 |
| 5G | 125,000 | 12.5 | 1,117 |
| 10G | 170,000 | 25 | 2,233 |
| 25G | 680,000 | 62.5 | 5,584 |
| 40G | 1,275,000 | 100 | 8,934 |
| 50G | 1,500,000 | 125 | 11,167 |
| 100G | 2,975,000 | 250 | 22,334 |
| 400G | 8,500,000 | 1000 | 89,335 |

*Annual Power Cost = (Power_W / 1000) × ₹10/unit × 24h × 365 days × 1.02*

---

## ⏱️ **Time Constants**

| Constant | Value | Description |
|----------|-------|-------------|
| Slot Duration | 0.5 ms (500 μs) | Radio frame time slot |
| Symbol Duration | 35.7 μs | OFDM symbol duration |
| Buffer (4 symbols) | 142.8 μs | Typical buffer delay |
| Buffer (10 symbols) | 357 μs | Maximum buffer delay |

---

## 🎚️ **Thresholds & Limits**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Target Utilization | 80% | Link capacity headroom |
| Peak Headroom | 100% | Must accommodate bursts |
| SLA High | ≥99% | Excellent performance |
| SLA Medium | 95-99% | Acceptable performance |
| SLA Low | <95% | Needs improvement |
| Max Loss Tolerance | 1% | Default packet loss limit |

---

## 📊 **Algorithm Complexity**

| Algorithm | Complexity | Iterations |
|-----------|-----------|------------|
| Binary Search | O(log n) | 15 iterations |
| Queue Simulation | O(n) | n = number of slots |
| Link Selection | O(k) | k = 9 speed tiers |
| Total Optimization | O(n × log n) | Per link |

---

## 🔢 **Example Scenarios**

### Scenario A: Light Traffic
- Peak: 2.5 Gbps, Optimized: 2.0 Gbps
- Recommended: **2.5G** (2.0 ≤ 2.5×0.8=2.0 ✓)
- CAPEX Savings: **20%**
- SLA Score: **99.8%**

### Scenario B: Heavy Traffic  
- Peak: 45 Gbps, Optimized: 32 Gbps
- Recommended: **40G** (32 ≤ 40×0.8=32 ✓, 45 > 40 ✗) → **50G**
- CAPEX Savings: **17%** (vs 50G)
- SLA Score: **99.2%**

### Scenario C: Bursty Traffic
- Peak: 15 Gbps, Optimized: 8 Gbps (with buffer)
- Recommended: **25G** (8 ≤ 25×0.8=20 ✓, 15 ≤ 25 ✓)
- CAPEX Savings: **47%** vs peak provisioning
- SLA Score: **99.5%**

---

**Last Updated:** 2026-02-01  
**Platform:** Nokia Fronthaul Capacity Optimizer v1.0
