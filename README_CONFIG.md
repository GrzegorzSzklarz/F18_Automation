# ASL F18 Bridge Automation: Configuration Manual

This document provides detailed instructions on how to configure the `config.json` file for the ASL F18 Measurement Matrix script.

---

## 1. JSON Configuration Template
The configuration file must be named `config.json` and located in the script's root directory. 

```json
{
    "thermometer_name": "SPRT_M1",
    "temperature": "TPW",
    
    "bridge_address": "GPIB0::4::INSTR",
    "bandwidth_hz_list": [0.1, 0.5],
    
    "points_per_step_list": [1000, 200],
    "gains_to_test": [0, 1, 2],
    
    "base_current_ma_list": [1.0, 2.0],
    "source_impedance_ohm": 100,
    
    "reference_resistor_name": "8138/01A",
    "reference_resistance": null,
    
    "SH_mode": 2,
    "SH_point_multipliers": [1, 2, 1]
}
```
---

## 2. Parameter Reference Table

| Parameter | Type | Description | Required? | Default |
| :--- | :--- | :--- | :--- | :--- |
| `thermometer_name` | String | ID of the sensor (used as a filename prefix). | **Yes** | "Unknown" |
| `temperature` | String | Temperature point (e.g., "0.01C", "Ga", "25C"). | **Yes** | "Unknown" |
| `bridge_address` | String | GPIB Resource string (e.g., "GPIB0::4::INSTR"). | No | Auto-scan |
| `bandwidth_hz_list` | List | Detector bandwidths to sweep (0.5, 0.1, 0.02). | No | `[0.5]` |
| `points_per_step_list` | List | Base points to collect (must match BW list length). | No | `[1000]` |
| `gains_to_test` | List | Gain levels to sweep (integer 0 to 7). | No | `[0, 1, 2]` |
| `base_current_ma_list`| List | Array of base currents in mA. | No | `[1.0]` |
| `source_impedance_ohm`| Int | Matching bridge impedance (1, 10, 100). | No | `100` |
| `reference_resistor_name`| String | Name of the standard from `resistors_db.csv`. | No | "" |
| `reference_resistance`| Float | Manual Ohm value if name is not in the database. | No | `null` |
| `SH_mode` | Int | Self-Heating logic mode (0, 1, or 2). | No | `0` |
| `SH_point_multipliers`| List | Scaling factors for each SH sub-phase. | No | `[1, 1, ...]` |

---

## 3. Reference Resistance ($R_{ref}$) Selection Logic

The script determines the reference value used for calculating $R_{meas} = Ratio \times R_{ref}$ based on a **3-level fallback system**:

1.  **Database Lookup**: If `reference_resistor_name` matches an entry in `resistors_db.csv`, that calibrated value is prioritized.
2.  **Manual Entry**: If the name is missing or not found in the CSV, the script looks for a numerical value in `reference_resistance`.
3.  **Hardware Default**: If both above are empty/null, the script defaults to the `source_impedance_ohm` value.

---

## 4. Self-Heating (SH) Modes

The `SH_mode` parameter determines how the script manages the bridge current for each entry in the `base_current_ma_list`. Testing for self-heating is a critical metrological procedure used to identify the temperature rise in the sensor caused by the measurement current itself.


### Mode 0: Standard (Dual-Step)
This is the default mode for routine self-heating checks and sensor characterization.
* **Sequence:** The script measures at the **Base Current** ($I$), then automatically switches to the **Excitation Current** ($\sqrt{2} \times I$, approximately $1.414 \times I$).
* **Metrological Purpose:** Since power $P = I^2 R$, multiplying the current by $\sqrt{2}$ results in **exactly doubling the power** dissipated in the sensor. This allows the user to extrapolate the resistance to "zero power" (the true temperature of the medium).
* **CSV Labels:** Data points are labeled as `1.0` and `1.0*1.41` (for a 1mA base).

### Mode 1: Single (Base Only)
This mode disables the self-heating sequence entirely.
* **Sequence:** The script measures **only** the **Base Current** ($I$) for the specified number of points and then moves to the next current level or gain.
* **Metrological Purpose:** Use this mode for fast sweeping of different current levels (e.g., verifying bridge linearity) or when the self-heating coefficient of the sensor is already well-known and does not need re-verification.
* **CSV Labels:** Data points are labeled with the base current value only (e.g., `1.0`).

### Mode 2: Metrological (Triple-Step with Recovery)
This is the most advanced mode, recommended for high-precision primary calibrations (e.g., ITS-90 fixed points) or stability studies.
* **Sequence:** **Base (Pre-Heat)** $\rightarrow$ **$\sqrt{2} \times I$ (Heating)** $\rightarrow$ **Base (Post-Heat/Recovery)**.
* **Metrological Purpose:** This mode allows for a complete **thermal recovery analysis**. By comparing the `Pre-Heat` and `Post-Heat` baselines at the same current, you can:
    1. Verify if the sensor returned to its original state.
    2. Detect any drift in the temperature of the calibration bath during the heating pulse.
    3. Calculate a more reliable average for the base resistance.
* **CSV Labels:** Data points are labeled as `1.0_pre`, `1.0*1.41`, and `1.0_post`.

---

### Pro-Tip: Using Multipliers with SH Modes

The `SH_point_multipliers` list works in tandem with the chosen mode to control the duration (number of points) of each sub-phase.

| If SH_mode is... | Multiplier List Example | Execution Logic |
| :--- | :--- | :--- |
| **0** (Standard) | `[1, 1]` | Equal time for Base and $\sqrt{2}$ phases. |
| **0** (Standard) | `[1, 3]` | Base phase is short; $\sqrt{2}$ phase is 3x longer to ensure thermal equilibrium. |
| **2** (Recovery) | `[1, 2, 1]` | Standard recovery test: Baseline, Double-length heat, Recovery baseline. |

**Example Calculation:**
If `points_per_step` is set to **500** and `SH_point_multipliers` is `[1, 4, 1]` in **Mode 2**:
* **Phase 1 (Pre):** 500 points
* **Phase 2 (Heat):** 2000 points
* **Phase 3 (Post):** 500 points

---

## 5. Point Multipliers and Timing

The `SH_point_multipliers` list allows you to scale the duration of specific phases relative to the `points_per_step_list`.

* **Calculation:** $\text{Points collected} = \text{base\_points} \times \text{multiplier}$

**Example Scenario (Mode 2):**
* `points_per_step_list`: `[1000]`
* `SH_mode`: `2`
* `SH_point_multipliers`: `[1, 5, 1]`
* **Execution:**
    1. **Pre-Heat:** 1000 points
    2. **Heating ($\sqrt{2}$):** 5000 points
    3. **Post-Heat:** 1000 points

> **Note on Stabilization:** After every change in Current or Gain, the script automatically waits for **10 x (1/Bandwidth)** seconds (e.g., 20s for 0.5Hz) to allow for thermal and electrical settling.

---

## 6. Output Files and Reporting

Files are automatically named using the pattern: `{thermometer}_{temperature}_{file_type}.extension`

### Data Files
* **Matrix Results (.csv):** Every raw data point with Timestamp, Ratio, Resistance ($\Omega$), Status, Gain, Current, and BW.
* **Summary Reports (.csv):** Statistical summaries including Mean Ratio, **Mean Resistance ($\Omega$)**, and:
    * **Standard Deviation ($StdDev$):** Indicates the measurement noise.
    * **Standard Error ($SEM$):** Indicates the statistical uncertainty of the mean: $SEM = \frac{StdDev}{\sqrt{n}}$.

### Visual Reports
* **Graphical Reports (.png):** A high-resolution plot generated after each Gain sequence. Each current level (and SH phase) is represented by a **unique color** and listed in the legend for easy comparison.

---