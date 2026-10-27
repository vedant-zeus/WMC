# PULSE-LTE: LTE Network Resource Management System

> **Course:** Wireless & Mobile Communications (WMC)  
> **Topic:** Downlink Radio Resource Management, Packet Scheduling & Energy Optimization in 4G LTE / 5G NR Networks  
> **Repository:** [https://github.com/vedant-zeus/WMC.git](https://github.com/vedant-zeus/WMC.git)

---

## 1. What is this Project Doing? (Executive Brief)

**PULSE-LTE** is a 3GPP-compliant software simulation system and live Network Operations Center (NOC) dashboard designed to solve the four central trade-offs in cellular network downlink communications:

1. **Spectral Efficiency vs. User Fairness:** High-rate users near the tower vs. weak users at cell edges.
2. **Real-Time Quality of Service (QoS):** Preventing packet drops for delay-critical traffic (VoIP & live video) under heavy cell congestion.
3. **Inter-Cell Interference (The "Flashlight Effect"):** Eliminating outdated CQI channel measurements caused by rapid neighbor cell scheduling variations.
4. **Base Station Power Consumption:** Slashing wasted electricity when cells have low or bursty traffic.

### What is PULSE?
**PULSE** stands for:
- **P**riority-**U**rgency Packet Scheduling (smooth exponential delay weighting bounded to prevent starvation).
- **L**ink Adaptation with Centralized Interference Coordination (**ICA** removes flashlight errors; **OLLA** dynamically tracks a 10% BLER target).
- **S**oft Frequency Reuse (**SFR**) that dynamically sizes edge/center power based on real-time cell-edge queue demand.
- **E**nergy Saving via QoS Slack-Aware Micro-Sleep (**ECO DTX**) allowing base stations to sleep in idle TTIs without violating latency deadlines.

### The 5 Schedulers Evaluated Head-to-Head
The system models an identical **7-cell hexagonal cellular network** with **105+ mobile users (UEs)** experiencing standardized 3GPP propagation, log-normal shadowing, and Jakes Rayleigh fading. It compares five packet scheduling algorithms under identical random drops and traffic seeds:

| Scheduler | Primary Objective | Key Trade-Off / Limitation |
|---|---|---|
| **Round Robin (RR)** | Maximize fairness across users | Completely ignores channel quality (CQI); lowest spectral efficiency; drops video under load. |
| **Max C/I** | Maximize instantaneous aggregate throughput | Pure opportunistic; completely starves cell-edge users with lower SINR (fairness breaks down). |
| **Proportional Fair (PF)** | Balance peak rates and past average throughput | 4G LTE industry standard; ignores packet deadlines, dropping up to 5% of video packets near capacity. |
| **M-LWDF** | Prioritize real-time queues with head-of-line delay | Linear delay weights cause latency volatility; vulnerable to channel estimation errors. |
| **PULSE (Proposed)** | Coordinated QoS, interference, frequency & energy management | Centralized C-RAN design cuts power by **39%**, cuts BLER from **45% to 11%**, and cuts video loss from **5.2% to 1.0%**. |

---

## 2. Quickstart: How to Run the Project

### Prerequisites
- Python 3.8+ (Tested on Python 3.10, 3.11, 3.12, 3.13)
- Required packages: `numpy`, `scipy`, `pandas`, `matplotlib`

```bash
# Clone the repository
git clone https://github.com/vedant-zeus/WMC.git
cd WMC
# (or cd pulse-lte if working locally in the repository folder)

# Install dependencies
pip install -r requirements.txt
```

---

### Step 1: Run the Automated Unit Test Suite
Verify physical layer functions, LTE resource allocation constraints, all 5 schedulers, and backend APIs:

```bash
python -m unittest discover -s tests -p "test_*.py"
```
*(All 13 tests run and pass in ~3.5 seconds with zero warnings)*

---

### Step 2: Launch the Telecom NOC Web Dashboard
Start the local classroom and demonstration server:

```bash
python serve.py
```

- **Open in Browser:** [http://localhost:8000](http://localhost:8000)
- **Optional CLI flags:**
  - `python serve.py --port 9000` (Use custom port)
  - `python serve.py --no-browser` (Don't open browser automatically)
  - `python serve.py --ip <IP>` (Override detected LAN IP for Wi-Fi hotspot)

---

### Step 3: Run Command-Line Simulation Benchmarks

```bash
# 1. Quick side-by-side verification across all 11 configurations (takes ~10 seconds)
python quick_check.py 50

# 2. Full Monte Carlo sweep across offered loads [0.3, 0.6, 0.9, 1.2, 1.5]
python experiments.py

# 3. Sensitivity studies (energy-delay tradeoff & CQI feedback delay)
python sensitivity.py

# 4. Generate all publication figures into results/
python plots.py
```

---

## 3. Dashboard Features & How to Demonstrate

The web dashboard is styled as a **Dark Navy Telecom Operations Center (NOC)** with cyan/electric blue accents and includes 6 interactive sections:

```
[Overview]  [Network Topology & PRB Allocation]  [Scheduler Comparison]  [Experiment Lab]  [WMC Educational Guide]  [BYOD Phone Join]
```

### 1. Overview HUD
- **Real-Time KPIs:** Cell throughput (Mbps), Spectral Efficiency (bps/Hz), Real-time QoS satisfaction (% of users meeting delay budgets), Block Error Rate (BLER %), Base station power consumption (Watts), and Energy Efficiency (kbit/J).
- **Power Sparkline:** Live rolling graph comparing power consumption between the selected baseline and PULSE over time.

### 2. Network Topology & Waterfall PRB Allocation
- **7-Cell Hexagonal Cluster:** Visualizes ISD 500 m macro layout. Mobile users (UEs) are color-coded by traffic class:
  - **Sky Blue:** VoIP users
  - **Orange:** HD Video users
  - **Emerald Green:** Best-Effort web download users
  - **Halos:** Cell-edge users with low geometry
- **Dual Waterfall PRB Grids (25 PRBs × 120 TTIs):** Displays frequency-time resource assignment side-by-side. View micro-sleep periods (slate), active allocations, and retransmitted NACK error blocks (crimson).
- **SFR Power Band Highlight:** Cyan bar indicating the protected edge sub-band for the selected cell.

### 3. 5-Scheduler Head-to-Head Comparison
- Click **"Run 5-Way Benchmark"** to evaluate Round Robin, Max C/I, Proportional Fair, M-LWDF, and PULSE under **identical channels, user positions, and fading paths**.
- Outputs a multi-column comparison table covering Throughput, BLER, VoIP latency, Video loss, Jain's Fairness, and DTX Sleep ratio.

### 4. Experiment Lab & Fault Injection
- **Network Knobs:** Sliders for offered load (0.2× to 1.8×), users per cell (5 to 30), mobility speed (3 to 120 km/h with Doppler shift calculation), traffic mix, and CQI feedback delay (1 to 10 ms).
- **PULSE Ablation Switches:** Toggle ICA, OLLA, SFR, or ECO DTX individually to demonstrate the contribution of each module.
- **Fault Injection:** Tap the map to fail a cell tower (tests handover/reattachment) or drop an external RF jammer (blasting PRBs 0–11).
- **Export to CSV:** Save experimental runs directly for post-processing.
- **AI Network Operator:** Integrates an AI operator that accepts plain English queries (e.g., *"What happens if cell 2 fails during rush hour?"*) and executes real experiments to answer.

### 5. WMC Educational Theory Guide
- Embedded reference guide covering LTE frame structure, PRB mathematics, eNodeB power modeling, CQI-to-MCS mapping, the Flashlight Effect, and scheduler formulas. Ideal for reference during oral defense or viva examination.

### 6. Bring Your Own Phone (BYOD) Mode
- Anyone in the room connected to the same Wi-Fi/hotspot can scan the on-screen QR code or open `http://<ip>:8000/#join`.
- The user's mobile device becomes a real mobile station (UE) inside the simulation. Move around the map, choose a service (Voice, Video, Download), and observe signal strength (SINR), CQI, modulation (QPSK/16QAM/64QAM), and throughput.

---

## 4. LTE System Parameters & Modeling Assumptions

| Parameter | Value | 3GPP Standard / Reference |
|---|---|---|
| **Carrier Frequency** | 2.0 GHz | Band 1 (FDD Downlink) |
| **System Bandwidth** | 5 MHz | **25 PRBs** |
| **Subcarrier Spacing** | 15 kHz | Normal Cyclic Prefix (12 subcarriers / PRB) |
| **Transmission Time Interval (TTI)** | 1.0 ms | 1 subframe = 2 slots of 0.5 ms |
| **Data Resource Elements (REs)** | 120 per PRB / TTI | 168 REs minus PDCCH (2 symbols) and CRS pilots |
| **Cell Layout** | 7-cell hexagonal cluster | Center cell + 1 tier ring; Inter-Site Distance (ISD) = 500 m |
| **eNodeB Transmit Power** | 43.0 dBm (20 Watts) | Distributed across active PRBs |
| **Path Loss Model** | $128.1 + 37.6 \log_{10}(d_{\text{km}})$ | 3GPP TR 36.814 Urban Macro |
| **Shadow Fading** | Log-normal, $\sigma = 8.0\text{ dB}$ | Correlated across cells |
| **Small-Scale Fast Fading** | Rayleigh fading per sub-band | Jakes AR(1) temporal correlation based on UE speed |
| **CQI Reporting** | 4-bit CQI (0–15) | 3GPP TS 36.213 Table 7.2.3-1 (4 ms feedback delay) |
| **HARQ Retransmission** | Synchronous HARQ | 8 ms Round Trip Time (RTT) upon NACK |
| **Base Station Energy Model** | EARTH Consortium macro model | $P_{\text{active}} = 130\text{W} + 4.7 \times 20\text{W} \times \frac{\text{PRBs}}{25}$; $P_{\text{sleep}} = 75\text{W}$ |

### Traffic Classes & Delay Budgets (QCI)
- **VoIP (QCI 1):** 328-bit AMR 12.2 kbps frames arriving every 20 ms. Hard deadline: **100 ms**.
- **HD Video (QCI 2):** Log-normal frame sizes arriving every 40 ms (25 fps, 450 kbps mean). Deadline: **300 ms**.
- **Best Effort (QCI 9):** Web file downloads with exponential burst sizes (80 kbit mean). Elastic traffic.

---

## 5. Mathematical Formulations of Schedulers

### 1. Round Robin (RR)
$$m_{i,k} = -t_{\text{last\_served}, i}$$
Allocates PRB $k$ to the eligible user served longest ago, cycling strictly in order.

### 2. Max C/I (Maximum Carrier-to-Interference)
$$m_{i,k} = r_{i,k}$$
Allocates PRB $k$ to the user with the highest instantaneous achievable rate $r_{i,k}$ derived from reported CQI.

### 3. Proportional Fair (PF)
$$m_{i,k} = \frac{r_{i,k}}{\bar{R}_i(t)}$$
Where $\bar{R}_i(t) = \left(1 - \frac{1}{t_c}\right) \bar{R}_i(t-1) + \frac{1}{t_c} R_i(t)$ is the exponential moving average throughput ($t_c = 100\text{ ms}$).

### 4. M-LWDF (Modified Largest Weighted Delay First)
$$m_{i,k} = a_i \cdot D_{\text{HOL}, i} \cdot \frac{r_{i,k}}{\bar{R}_i(t)}, \quad a_i = -\frac{\ln(\delta_i)}{\tau_i}$$
Where $D_{\text{HOL}, i}$ is head-of-line packet delay, $\tau_i$ is delay deadline (100 ms VoIP, 300 ms video), and $\delta_i$ is maximum allowed drop probability (0.05).

### 5. PULSE (Proposed Integrated Scheme)
$$m_{i,k} = w_{\text{class}}(i) \cdot U_i(t) \cdot \text{pref}_{\text{SFR}}(i,k) \cdot \frac{r_{i,k}}{\bar{R}_i(t)}$$
- **Class Weights:** $w_{\text{class}} = 2.0$ (VoIP), $1.5$ (Video), $1.0$ (Best Effort).
- **Bounded Urgency Exponent:**
  $$U_i(t) = \begin{cases} 1.0 & \text{for Best Effort} \\ \exp\left(\min\left(4 \cdot \frac{D_{\text{HOL}, i}}{\tau_i}, 6.0\right)\right) & \text{for Real-Time}\end{cases}$$
  Grows smoothly from $1.0$ to $\approx 55\times$, prioritizing packets approaching deadlines before drops occur.
- **Interference-Coordinated Link Adaptation (ICA):** Corrects reported SINR using centralized knowledge of neighbor cell transmit states:
  $$\text{SINR}_{\text{corrected}} = \text{SINR}_{\text{reported}} \cdot \frac{N_0 + I_{\text{measurement}}}{N_0 + I_{\text{now}}}$$
- **Outer-Loop Link Adaptation (OLLA):** Adjusts SINR offset targeting 10% BLER: $+0.056\text{ dB}$ on ACK, $-0.5\text{ dB}$ on NACK.
- **Slack-Aware Micro-Sleep (ECO DTX):** If all queued real-time packets have used $< 15\%$ of their delay budget, traffic is temporarily held so the base station can power down to $75\text{ W}$ for that TTI.

---

## 6. Project Directory Structure

```
pulse-lte/
├── pulse/                    # Core Python Simulation Engine
│   ├── __init__.py           # Package exports (SimConfig, LTESimulator)
│   ├── config.py             # Dataclass configuration & scenario toggles
│   ├── phy.py                # 3GPP TS 36.213 CQI table, BLER curves & MCS efficiency
│   ├── schedulers.py         # Downlink schedulers: RR, Max C/I, PF, M-LWDF, PULSE
│   └── simulator.py          # TTI-level multi-cell LTE simulation engine
├── tests/                    # Automated Unit Test Suite
│   ├── __init__.py
│   ├── test_simulation.py    # PHY, scheduler constraints & simulator domain tests
│   └── test_server.py        # HTTP server & REST API unit tests
├── dashboard/                # Modern Telecom NOC Web Dashboard
│   ├── index.html            # Single-page interactive NOC console
│   └── vendor/
│       └── qrcode.min.js     # QR code generator for BYOD mobile join (offline)
├── results/                  # Generated Figures and Benchmark Datasets
│   ├── summary.csv           # Multi-seed sweep summary across loads
│   ├── raw_results.csv       # Raw simulation output records
│   └── *.png                 # Publication figures (BLER, throughput, power, ablation)
├── serve.py                  # NOC web server with REST APIs (/api/simulate, /api/compare)
├── quick_check.py            # Quick multi-scheme verification script
├── experiments.py            # Full Monte Carlo simulation sweep runner
├── sensitivity.py            # Energy-delay and CQI feedback delay studies
├── plots.py                  # Matplotlib script generating report figures
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 7. REST API Documentation

The server (`serve.py`) provides endpoints for running simulations programmatically:

### 1. `POST /api/simulate`
Runs an exact Python simulation and returns performance metrics.
```json
// Request Body
{
  "config": {
    "scheduler": "pulse",
    "load_scale": 0.8,
    "n_tti": 300,
    "seed": 42,
    "users_per_cell": 15,
    "speed_kmh": 30,
    "cqi_delay_tti": 4,
    "olla": true,
    "ica": true,
    "sfr": true,
    "energy": true,
    "eco_batching": true
  }
}
```

### 2. `POST /api/compare`
Runs all 5 schedulers across the exact same channel realization and returns side-by-side results.
```json
// Request Body
{
  "schedulers": ["rr", "maxci", "pf", "mlwdf", "pulse"],
  "config": {
    "load_scale": 0.8,
    "n_tti": 200,
    "seed": 1
  }
}
```

### 3. `GET /api/schemes`
Returns the metadata, description, and classification of all 5 supported schedulers.

### 4. `GET /api/summary`
Returns the pre-computed benchmark dataset across loads from `results/summary.csv`.

---

## 8. Academic Disclosure & Simulation Limitations

> [!NOTE]
> **Academic Model Notice:** This project is a software-based discrete-time (1 TTI = 1 ms) numerical simulator of an LTE downlink cellular system, modeled according to 3GPP specifications. It is intended for academic evaluation and research, not hardware radio transmission.

1. **Simulation Scope:** Downlink data transmission only; uplink is modeled via feedback delays (CQI delay: 4 ms, HARQ RTT: 8 ms).
2. **Channel Assumptions:** Rayleigh fading channel per CQI sub-band (5 PRBs) with Clarke/Jakes Doppler autocorrelation. Spatial multi-antenna MIMO and carrier aggregation are simplified to a single 5 MHz SISO carrier.
3. **Hardware Boundaries:** Web browsers in BYOD mode cannot access baseband hardware registers due to mobile OS security restrictions. Device positions and services drive simulated UEs inside the 3GPP propagation engine.

---

## 9. Viva & Oral Exam Preparation (Cheat Sheet)

**Q1: Why not simply use Proportional Fair (PF)?**  
*Answer:* PF balances throughput and long-term fairness, but is completely delay-agnostic. At 0.9× load, video packets near their deadline are dropped because PF waits for a favorable channel peak that comes too late. PULSE's bounded urgency term prioritizes packets before deadlines expire.

**Q2: How does Centralized ICA solve the Flashlight Effect?**  
*Answer:* UE CQI measurements are 4 ms old. In a dynamic network, neighbor cells that were idle during measurement may transmit now, causing an unexpected interference surge. Operating as a centralized C-RAN controller with full awareness of neighbor PRB allocations, PULSE computes the exact ratio of measurement-time to current-time interference: $\frac{N_0 + I_{\text{then}}}{N_0 + I_{\text{now}}}$ and corrects the SINR before modulation selection.

**Q3: How does Cell DTX save energy without violating QoS?**  
*Answer:* At low loads, real-time packets use only a small fraction of their delay budget (e.g. VoIP packets arriving every 20 ms with 100 ms budget). Instead of waking the base station amplifier every millisecond for tiny transmissions, PULSE's ECO module batches traffic over 10–15 ms, allowing the base station to enter micro-sleep ($75\text{ W}$ instead of $130\text{ W}+$) without violating user deadlines.

---

## 10. References

1. **3GPP TS 36.213:** *E-UTRA Physical layer procedures* — CQI table, AMC, link adaptation.
2. **3GPP TR 36.814:** *Further advancements for E-UTRA physical layer aspects* — Macro pathloss & urban simulation methodology.
3. **F. Capozzi et al. (IEEE Comms Surveys & Tutorials, 2013):** *"Downlink packet scheduling in LTE cellular networks: Key design issues and a survey."*
4. **M. Andrews et al. (IEEE Communications Magazine, 2001):** *"Providing quality of service over a shared wireless link"* (M-LWDF algorithm).
5. **K. I. Pedersen et al. (IEEE VTC, 2007):** *"Frequency domain scheduling for OFDMA with limited and noisy channel feedback"* (OLLA).
6. **Huawei (3GPP TSG RAN WG1, R1-050507):** *"Soft frequency reuse scheme for UTRAN LTE."*
7. **G. Auer et al. (IEEE Wireless Communications, 2011):** *"How much energy is needed to run a wireless network?"* (EARTH base station energy model).
8. **P. Frenger et al. (IEEE VTC, 2011):** *"Reducing energy consumption in LTE with cell DTX."*
