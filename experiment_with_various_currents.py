import time
import os
import json
import csv
import sys
import numpy as np
from datetime import datetime
from collections import deque
import matplotlib.pyplot as plt
import matplotlib

# Import the custom F18 control class from our library
from F18_commands import F18Commands

try:
    matplotlib.use('QtAgg') 
except:
    pass

# =============================================================================
# --- EXPERIMENT CONFIGURATION FROM JSON & CSV ---
# =============================================================================

def load_resistor_db(filepath):
    """Loads the resistor database from a CSV file into a dictionary."""
    db = {}
    if os.path.exists(filepath):
        with open(filepath, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Key: Name, Value: Resistance as float
                db[row['Name'].strip()] = float(row['Resistance'])
    else:
        print(f"[WARNING] Resistor database file '{filepath}' not found!")
    return db

# 1. Load the JSON configuration file
config_path = "config.json"
if not os.path.exists(config_path):
    raise FileNotFoundError(f"Configuration file not found: {config_path}")

with open(config_path, "r") as f:
    config = json.load(f)

# 2. Extract experiment metadata
THERMOMETER_NAME = config.get("thermometer_name", "UnknownThermometer")
TEMPERATURE = config.get("temperature", "UnknownTemp")

# Auto-generate file names with the required prefix
prefix = f"{THERMOMETER_NAME}_{TEMPERATURE}_"

OUTPUT_FILE_NAME = prefix + config.get("output_file_base", "matrix_results.csv")
REPORT_ALL_FILE = prefix + config.get("report_all_base", "report_all.csv")
REPORT_BALANCED_FILE = prefix + config.get("report_balanced_base", "report_balanced.csv")

# 3. Hardware and loop parameters
DEFAULT_BRIDGE_ADDR = config.get("bridge_address", "GPIB0::4::INSTR")
BANDWIDTH_HZ_LIST = config.get("bandwidth_hz_list", [0.5])
POINTS_PER_STEP_LIST = config.get("points_per_step_list", [1000])

assert len(BANDWIDTH_HZ_LIST) == len(POINTS_PER_STEP_LIST), "BANDWIDTH and POINTS lists must be the same size!"

GAINS_TO_TEST = config.get("gains_to_test", [1, 10, 100])
BASE_CURRENT_MA_LIST = config.get("base_current_ma_list", [1.0])
SOURCE_IMPEDANCE_OHM = config.get("source_impedance_ohm", 100)

# Self-Heating Mode Configuration
SH_MODE = config.get("SH_mode", 0)
SH_MULTIPLIERS = config.get("SH_point_multipliers", None)

# Default multipliers if not defined in JSON
if SH_MULTIPLIERS is None:
    if SH_MODE == 0: SH_MULTIPLIERS = [1.0, 1.0]
    elif SH_MODE == 1: SH_MULTIPLIERS = [1.0]
    elif SH_MODE == 2: SH_MULTIPLIERS = [1.0, 1.0, 1.0]

# 4. Determine Reference Resistance (The 3-Step Fallback Logic)
resistor_db = load_resistor_db("resistors_db.csv")

ref_name = config.get("reference_resistor_name", "")
ref_val_json = config.get("reference_resistance", None)

if ref_name and ref_name in resistor_db:
    # Option A: Name provided and found in CSV database
    REF_RESISTANCE = resistor_db[ref_name]
    print(f"[CONFIG] Found reference resistor '{ref_name}' in DB: {REF_RESISTANCE} Ohm")
    
elif ref_val_json is not None and str(ref_val_json).strip() != "":
    # Option B: Name not found/provided, but manual resistance value is in JSON
    REF_RESISTANCE = float(ref_val_json)
    print(f"[CONFIG] Using manually provided reference resistance from JSON: {REF_RESISTANCE} Ohm")
    
else:
    # Option C: Neither name nor manual value is valid, fallback to source impedance
    REF_RESISTANCE = float(SOURCE_IMPEDANCE_OHM)
    print(f"[CONFIG] No valid reference name or value provided. Falling back to Source Impedance: {REF_RESISTANCE} Ohm")

# =============================================================================

STATUS_PLOT_VAL = {'B': 3, 'L': 2, 'H': 1, 'E': 0}

# --- ATTEMPT CONNECTION WITH AUTO-SCAN ---
f18 = None

try:
    f18 = F18Commands(DEFAULT_BRIDGE_ADDR)
except SystemExit:
    print("[INFO] Default address failed. Starting intelligent scan...")
    found_addr = F18Commands.scan_for_bridge()
    if found_addr:
        f18 = F18Commands(found_addr)
    else:
        print("[FATAL] No F18 bridge found on any GPIB address. Exiting.")
        sys.exit()

# --- LIVE PLOT SETUP ---
plt.ion()
fig_live, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
fig_live.canvas.manager.set_window_title('ASL F18 - Automated Test Matrix')

line_ratio, = ax1.plot([], [], 'b-', linewidth=1, label="Ratio")
line_status, = ax2.step([], [], 'r-', where='post', label="Status")

ax1.set_ylabel("Resistance Ratio")
ax1.grid(True, alpha=0.3)
ax1.set_title("Real-time Measurement Data")

ax2.set_ylabel("Status (3=Balanced)")
ax2.set_ylim(-0.5, 3.5)
ax2.grid(True, alpha=0.3)
ax2.set_xlabel("Global Measurement Index")

max_plot_points = 2000
x_display = deque(maxlen=max_plot_points)
y_ratio = deque(maxlen=max_plot_points)
y_status = deque(maxlen=max_plot_points)

def save_sequence_plot(gain, bandwidth, segments):
    """Saves a plot where each current is a separate colored series."""
    if not segments: return
    plt.ioff()
    fig_save, (s_ax1, s_ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    current_x = 0
    all_status_combined = []
    
    for label, ratios, status_nums in segments:
        x_vals = range(current_x, current_x + len(ratios))
        s_ax1.plot(x_vals, ratios, label=f"I: {label} mA")
        all_status_combined.extend(status_nums)
        current_x += len(ratios)
    
    s_ax1.set_title(f"Gain {gain} | BW {bandwidth}Hz | {THERMOMETER_NAME} @ {TEMPERATURE}")
    s_ax1.set_ylabel("Ratio")
    s_ax1.legend(loc='upper right', fontsize='small', ncol=2)
    s_ax1.grid(True, alpha=0.3)
    
    s_ax2.step(range(len(all_status_combined)), all_status_combined, 'k-', where='post')
    s_ax2.set_ylabel("Status")
    s_ax2.set_ylim(-0.5, 3.5)
    
    fname = f"Report_BW{bandwidth}Hz_G{gain}_{datetime.now().strftime('%H%M%S')}.png"
    plt.savefig(fname)
    plt.close(fig_save)
    plt.ion()
    print(f"[INFO] Saved color-coded plot: {fname}")
    
def append_stats_report(filename, current_label, gain, bw, data_list, ref_val):
    """Appends summary statistics including Ratio and Resistance."""
    with open(filename, "a") as f:
        n = len(data_list)
        if n == 0:
            f.write(f"{current_label},{gain},{bw},NaN,NaN,NaN,NaN,NaN,NaN\n")
        else:
            mean_ratio = np.mean(data_list)
            mean_res = mean_ratio * ref_val
            std_ratio = np.std(data_list, ddof=1) if n > 1 else 0.0
            sem_ratio = std_ratio / np.sqrt(n)
            
            # Columns: Current, Gain, BW, Mean_Ratio, Mean_Resistance, Std_Ratio, SEM_Ratio, Min, Max
            f.write(f"{current_label},{gain},{bw},{mean_ratio:.8f},{mean_res:.8f},"
                    f"{std_ratio:.8e},{sem_ratio:.8e},{np.min(data_list):.8f},{np.max(data_list):.8f}\n")

# --- EXPERIMENT START ---
try:
    print("--- STARTING HARDWARE INITIALIZATION ---")
    f18.online()
    f18.auto_balance()
    f18.set_source_impedance(SOURCE_IMPEDANCE_OHM)
    
    # Initialize report files with headers if they don't exist
    for rep_file in [REPORT_ALL_FILE, REPORT_BALANCED_FILE]:
        if not os.path.exists(rep_file):
            with open(rep_file, "w") as f:
                f.write("Current_mA,Gain,Bandwidth_Hz,Mean_Ratio,Mean_Resistance_Ohm,Std_Ratio,SEM_Ratio,Min_Ratio,Max_Ratio\n")

    write_header = not os.path.exists(OUTPUT_FILE_NAME)

    with open(OUTPUT_FILE_NAME, "a") as file:
        if write_header:
            file.write("Date,Time,Ratio,Resistance_Ohm,Status,Gain,Current_mA,Bandwidth_Hz\n")
        
        global_idx = 0

        # LEVEL 1: Sweep through Bandwidths
        for bw_idx, current_bw in enumerate(BANDWIDTH_HZ_LIST):
            base_pts_for_this_bw = POINTS_PER_STEP_LIST[bw_idx]
            pts_for_this_bw = POINTS_PER_STEP_LIST[bw_idx]
            
            # Recalculate time required for one measurement point based on bandwidth
            DELAY_SEC = 1.0 / current_bw
            
            print("\n============================================================")
            print(f" >>> PHASE: BANDWIDTH {current_bw} Hz | POINTS PER STEP: {pts_for_this_bw} <<<")
            print("============================================================")
            f18.set_bandwidth(current_bw)

            # LEVEL 2: Sweep through Gain levels
            for current_gain in GAINS_TO_TEST:
                print(f"\n--- SWITCHING TO GAIN LEVEL: {current_gain} ---")
                f18.set_gain(current_gain)
                
                # Use a list to store segments for the multi-colored plot
                gain_segments = []
                
                # LEVEL 3: Sweep through Base Currents
                for base_curr in BASE_CURRENT_MA_LIST:
                    
                    # --- Determine sequence of steps based on SH_MODE ---
                    sequence_steps = []
                    if SH_MODE == 0:
                        # Standard Mode: Base -> SH
                        sequence_steps.append({"is_sqrt2": False, "mult": SH_MULTIPLIERS[0], "label": str(base_curr)})
                        sequence_steps.append({"is_sqrt2": True,  "mult": SH_MULTIPLIERS[1], "label": f"{base_curr}*1.41"})
                    elif SH_MODE == 1:
                        # Base Only Mode
                        sequence_steps.append({"is_sqrt2": False, "mult": SH_MULTIPLIERS[0], "label": str(base_curr)})
                    elif SH_MODE == 2:
                        # Base -> SH -> Base (Recovery) Mode
                        sequence_steps.append({"is_sqrt2": False, "mult": SH_MULTIPLIERS[0], "label": f"{base_curr}_pre"})
                        sequence_steps.append({"is_sqrt2": True,  "mult": SH_MULTIPLIERS[1], "label": f"{base_curr}*1.41"})
                        sequence_steps.append({"is_sqrt2": False, "mult": SH_MULTIPLIERS[2], "label": f"{base_curr}_post"})
                    
                    # Execute the current sequence
                    for step in sequence_steps:
                        enable_sqrt2 = step["is_sqrt2"]
                        current_label = step["label"]
                        multiplier = step["mult"]
                        pts_to_collect = int(base_pts_for_this_bw * multiplier)
                        
                        f18.set_current(base_curr, sqrt2_multiplier=enable_sqrt2)
                        print(f"\n[STARTING] Gain: {current_gain} | Current: {current_label} mA | Pts: {pts_to_collect}")
                        
                        # -------------------------------------------------------------
                        # 1. SMART AUTO-STABILIZATION (Prevents recording garbage data)
                        # -------------------------------------------------------------
                        max_stab_time = max(60, int(DELAY_SEC * 15))
                        print(f"[WAIT] Waiting for bridge stabilization (max {max_stab_time} s)...")
                        
                        stab_start_time = time.time()
                        consecutive_b = 0
                        required_b = 5  # Target: 5 consecutive 'B' (Balanced) statuses
                        
                        while (time.time() - stab_start_time) < max_stab_time:
                            data = f18.get_measurement()
                            if data is not None:
                                s = data['status_code']
                                if s == 'B':
                                    consecutive_b += 1
                                    if consecutive_b >= required_b:
                                        print(f"[INFO] Bridge stabilized ({required_b}x 'B'). Stabilization time: {int(time.time() - stab_start_time)} s.")
                                        break
                                else:
                                    consecutive_b = 0  # Reset counter if bridge loses balance
                            
                            # Sleep dynamically based on bandwidth to avoid spamming the GPIB port
                            time.sleep(max(1.0, DELAY_SEC * 0.5))
                            plt.pause(0.01) # Keep the plot GUI responsive
                            
                        if consecutive_b < required_b:
                            print(f"[WARNING] Stabilization timeout reached! Starting measurement anyway (Check parameters for {current_label} mA).")
                        
                        # -------------------------------------------------------------
                        # 2. DATA COLLECTION LOOP
                        # -------------------------------------------------------------
                        step_ratios_all = []
                        step_status_plot = []
                        step_ratios_balanced = []
                        
                        points_collected = 0
                        while points_collected < pts_to_collect:
                            data = f18.get_measurement()
                            
                            if data is not None:
                                now = datetime.now()
                                r, s = data['ratio'], data['status_code']
                                resistance_ohm = r * REF_RESISTANCE
                                
                                timestamp = now.strftime('%Y-%m-%d,%H:%M:%S')
                                file.write(f"{timestamp},{r:.8f},{resistance_ohm:.8f},{s},{current_gain},{current_label},{current_bw}\n")
                                file.flush()
                                
                                step_ratios_all.append(r)
                                step_status_plot.append(STATUS_PLOT_VAL.get(s, 0))
                                if s == 'B': 
                                    step_ratios_balanced.append(r)
                                
                                global_idx += 1
                                x_display.append(global_idx)
                                y_ratio.append(r)
                                y_status.append(STATUS_PLOT_VAL.get(s, 0))
                                
                                # Update plot only every 5 points to save CPU resources
                                if points_collected % 5 == 0:
                                    line_ratio.set_data(range(len(y_ratio)), y_ratio)
                                    line_status.set_data(range(len(y_status)), y_status)
                                    ax1.relim()
                                    ax1.autoscale_view()
                                    ax2.relim()
                                    ax2.autoscale_view()
                                    plt.pause(0.01)
                                    
                                    print(f"BW:{current_bw} | G:{current_gain} | I:{current_label}mA | Pkt:{points_collected+1}/{pts_to_collect} | R:{r:.8f} | S:{s}")
                                
                                points_collected += 1
                                
                                # This prevents 'VI_ERROR_CONN_LOST' by giving the bridge time to compute.
                                time.sleep(DELAY_SEC * 0.9)
                            
                            else:
                                # If communication fails momentarily, wait 1 second and retry
                                time.sleep(1.0)
                                
                        # Save statistical data for the completed step
                        gain_segments.append((current_label, step_ratios_all, step_status_plot))
                        append_stats_report(REPORT_ALL_FILE, current_label, current_gain, current_bw, step_ratios_all, REF_RESISTANCE)
                        append_stats_report(REPORT_BALANCED_FILE, current_label, current_gain, current_bw, step_ratios_balanced, REF_RESISTANCE)
                
                # Generate and save the plot for the current gain step
                save_sequence_plot(current_gain, current_bw, gain_segments)
                        
    print("\n[SUCCESS] Entire experiment matrix completed successfully.")

except KeyboardInterrupt:
    print("\n[WARNING] Experiment manually interrupted by user (Ctrl+C).")
except Exception as e:
    print(f"\n[ERROR] An unexpected error occurred: {e}")
finally:
    print("\n--- SHUTTING DOWN AND CLEANING UP ---")
    if f18 is not None: 
        try:
            f18.offline()
        except:
            print("[INFO] Could not send OFL command (Connection already lost).")
        
        try:
            f18.close()
        except:
            pass
    
    print("Execution finished.")
    plt.ioff()
    plt.show()