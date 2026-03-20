# ASL F18 Bridge Automation Suite

A professional Python-based automation tool for characterizing resistance thermometers using the **ASL F18 Resistance Bridge** via GPIB. This suite enables automated sweeps of Bandwidth, Gain, and Current, including advanced Self-Heating (SH) analysis.

---

## 🌟 Key Features
- **Automated Matrix:** Sweeps through multiple bandwidths, gains, and currents without manual intervention.
- **Smart Auto-Stabilization:** Intelligent "Wait-for-Balance" logic that starts recording only when the bridge is stable (Status B).
- **High-Performance Live Plotting:** Powered by **PyQtGraph** for smooth, lag-free real-time visualization of thousands of points.
- **Advanced SH Logic:** Supports Standard (Base/Sqrt2), Single, and Metrological (Pre-heat/Heat/Post-heat) recovery modes.
- **Intelligent Error Handling:** Automatic session recovery and "Headless" report generation to prevent crashes during long runs.
- 
---

## 🛠️ Prerequisites

### Hardware
- **ASL F18** Temperature Bridge.
- **GPIB Interface** (e.g., NI GPIB-USB-HS or compatible).

### Software
- **NI-VISA Drivers:** You must install the [National Instruments VISA driver](https://www.ni.com/en-gb/support/downloads/drivers/download.ni-visa.html) for GPIB communication.
- **Python 3.8+**
- **PyQtGraph & PySide6:** For the high-speed live monitor.

---

## 📥 Installation

1. Clone this repository:
   ```bash
   git clone [https://github.com/GrzegorzSzklarz/F18-Automation.git](https://github.com/GrzegorzSzklarz/F18-Automation.git)
   cd F18-Automation
   ```
   
### 2. Install Required Python Packages
It is recommended to use a virtual environment (venv) or a Conda environment to avoid conflicts:
**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Required Packages
Install all necessary libraries using the provided `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## 📁 Project Structure

```text
.
├── experiment_main.py      # Main execution script
├── F18_commands.py         # Hardware driver & GPIB communication library
├── config.json             # Experiment configuration (Matrix, SH modes)
├── resistors_db.csv        # Database for standard resistors
├── requirements.txt        # List of Python dependencies
├── LICENSE                 # MIT License details
├── README.md               # Main documentation
└── README_CONFIG.md        # Technical guide for configuration
├── Results/                # AUTO-GENERATED: Experiment data & reports
│   └── {Sensor}_{Temp}/    # Subfolder for specific test runs
│       ├── ..._results.csv # Raw data log
│       ├── ..._report.csv  # Statistical summaries
│       └── Report_...png   # Automated color-coded plots
```

---

## ⚙️ Configuration

The automation suite is designed for flexibility, allowing you to run complex experiments without modifying the Python source code. It relies on two primary configuration files located in the root directory.

### 1. `config.json`
This is the main control file. It defines the measurement matrix and experimental conditions. Key parameters include:

* **Metadata:** `thermometer_name` and `temperature` (used for automated file naming).
* **Hardware Settings:** `bridge_address` (GPIB string) and `source_impedance_ohm` (1, 10, or 100 $\Omega$).
* **Measurement Matrix:** Lists for `bandwidth_hz_list`, `gains_to_test`, and `base_current_ma_list`.
* **SH Logic:** * `SH_mode`: Selects the Self-Heating routine (0: Standard, 1: Single, 2: Recovery).
    * `SH_point_multipliers`: Sets the duration ratio for each measurement sub-phase.

### 2. `resistors_db.csv`
A dedicated database for your laboratory's calibrated standard resistors. The script uses this file to perform real-time conversion from Resistance Ratio to Ohms ($\Omega$).

**Format:**
```csv
Name,Resistance
Standard_100,100.0004971
Standard_25,25.0001798
```

> 📘 **Advanced Configuration:** For a comprehensive technical breakdown of every JSON parameter and best metrological practices, please refer to the [**README_CONFIG.md**](README_CONFIG.md) file.

---

## 🚀 Usage

Once your `config.json` and `resistors_db.csv` are properly configured, you can initiate the automated measurement matrix.

### 1. Start the Experiment
Run the main script from your terminal or command prompt:

```bash
python experiment_main.py
```

## 2. Execution Workflow
The script follows a rigorous metrological procedure to ensure data integrity during every measurement cycle:

1.  **Hardware Initialization:** The system attempts to connect to the ASL F18 bridge. If the default address fails, it automatically performs an intelligent scan of all GPIB addresses (0–31).
2.  **Parameter Setup:** The bridge is configured with the first set of parameters from your matrix, including **Bandwidth**, **Gain**, and **Excitation Current**.
3. **Smart Stabilization & Dynamic Wait State:** The script employs an active feedback loop that monitors the bridge status in real-time. Data collection begins after achieving 5 consecutive "Balanced" (B) readings, ensuring full thermal and electronic equilibrium. If stability is not reached within a safety timeout, the system logs a warning but starts to collect data to prevent hanging on a single problematic setting.
4.  **Data Collection:** Points are collected according to the values defined in the `points_per_step_list`.
5.  **Real-time Monitoring:**
    * **Live Plot:** A dedicated window displays the last 2000 points of the Resistance Ratio and the Bridge Balance status.
    * **Console Output:** The terminal prints real-time statistics, including the current point count, ratio value, and bridge status (e.g., `B` for Balanced).

---

## 3. Safety and Data Integrity
The suite is built to protect your measurement data during long-term or unattended runs:

* **Auto-Flush:** Every single measurement is written to the CSV file and "flushed" to the disk immediately. In the event of a power failure or system crash, you will only lose the most recent data point.
* **Manual Interruption:** You can safely stop the experiment at any time by pressing **`Ctrl+C`**. The script will gracefully:
    1. Stop the active measurement loop.
    2. Send an `OFL` (Offline) command to return the F18 bridge to **Local Mode**.
    3. Close the GPIB session properly to avoid hanging the interface.

---

## 4. Monitoring the Bridge Status
When observing the live plot or console logs, pay close attention to the **Status Codes** returned by the F18 bridge:

| Code | Meaning | Description |
| :--- | :--- | :--- |
| **B** | **Balanced** | Measurement is stable, valid, and ready for recording. |
| **L / H** | **Low / High** | Bridge is out of balance. Common during the first few seconds after a current change. |
| **E** | **Error** | Communication or hardware error detected. Check cables and bridge settings. |

> 📘 **Pro-Tip:** For long-term (overnight) measurements, ensure your PC's **"Sleep Mode"** and **"USB Selective Suspend"** are disabled to prevent the GPIB connection from timing out.

---


## 📊 Data Output & Reporting
To keep your workspace organized, the script automatically creates a dedicated subfolder for each experiment. All outputs are saved in the following directory structure:
**`Results/{Thermometer}_{Temperature}/`**

Inside this specific directory, all files are further organized with the `{Thermometer}_{Temperature}_` prefix to prevent data mixing:

* **`..._matrix_results.csv`**: The primary data log containing raw ratios, converted resistance values ($\Omega$), and real-time bridge status.
* **`..._report_all.csv`**: Statistics calculated from *every* data point collected during the step, including transitional and out-of-balance points.
* **`..._report_balanced.csv`**: Statistics strictly filtered for **"Balanced" (Status B)** points only—**highly recommended** for deriving your final calibration values.
* **`Report_BW...png`**: High-quality, automatically generated plots where each current step is visualized as a separate, color-coded series.
---

## ⚖️ License

This project is licensed under the **MIT License** - see the [**LICENSE**](LICENSE) file for details.

Copyright (c) 2026 Grzegorz Szklarz


