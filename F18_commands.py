import pyvisa
import sys
import time

class F18Commands:
    """
    A complete class to control the ASL F18 Thermometry Bridge via GPIB using PyVISA.
    This module implements the full set of commands available in the F18 manual.
    """

    def __init__(self, resource_string):
        """
        Initializes the connection to the F18 bridge.
        
        Args:
            resource_string (str): The VISA resource name, e.g., 'GPIB0::4::INSTR'.
        """
        self.rm = pyvisa.ResourceManager()
        try:
            self.bridge = self.rm.open_resource(resource_string)

            self.bridge.timeout = 15000       
            self.bridge.clear()            
            
            self.bridge.read_termination = '\r\n'
            self.bridge.write_termination = '\r\n'
            
            self.bridge.send_end = True         
            self.bridge.delay_after_write = 0.1
            
            import time
            time.sleep(1.0)
            
            # Internal variable to track status of the meter (default 0)
            self._meter_mode = 0
            
            print(f"[INFO] Successfully connected to: {resource_string}")
        except Exception as e:
            print(f"[ERROR] CONNECTION FAILED: {e}")
            sys.exit(1)

    # =========================================================================
    # SYSTEM & MODE COMMANDS (ONL, OFL, AU, MAN)
    # =========================================================================

    def online(self):
        """Sets the bridge to remote control mode (ONL)."""
        self.bridge.write("ONL")
        print("[INFO] Bridge set to ONLINE mode.")

    def offline(self):
        """Sets the bridge to local front-panel control mode (OFL)."""
        self.bridge.write("OFL")
        print("[INFO] Bridge set to OFFLINE mode (Local control).")

    def auto_balance(self):
        """Enables the continuous Auto Balance mode (AU)."""
        self.bridge.write("AU")
        print("[INFO] Auto Balance mode enabled.")

    def manual_balance(self):
        """Sets the bridge to Manual Balance mode (MAN)."""
        self.bridge.write("MAN")
        print("[INFO] Manual Balance mode enabled.")

    # =========================================================================
    # CONFIGURATION COMMANDS (B, C, G, SRC, FRQ, MET, REF)
    # =========================================================================

    def set_bandwidth(self, hz):
        """
        Sets the detector bandwidth (B command).
        
        Args:
            hz (float): Bandwidth in Hertz. Allowed: 0.5, 0.1, 0.02.
        """
        bw_map = {0.5: 0, 0.1: 1, 0.02: 2}
        if hz in bw_map:
            self.bridge.write(f"B{bw_map[hz]}")
            print(f"[INFO] Bandwidth set to {hz} Hz.")
        else:
            raise ValueError(f"Invalid bandwidth. Allowed (Hz): {list(bw_map.keys())}")
            
    def set_check_mode(self, code):
        """
        Sets the internal check mode of the instrument (CHK command).
        
        Args:
            code (int): 
                0 = Normal operation (no check)
                1 = Zero check
                2 = Unit check
        """
        if code in [0, 1, 2]:
            self.bridge.write(f"CHK{code}")
            status_desc = ["Normal operation", "Zero check", "Unit check"][code]
            print(f"[INFO] Check mode (CHK) set to {code}: {status_desc}.")
        else:
            raise ValueError("Invalid check mode. Allowed codes: 0, 1, 2.")

    def set_current(self, current_ma, sqrt2_multiplier=False):
        """
        Sets the measurement current (C command).
        
        Args:
            current_ma (float): Base current in mA.
            sqrt2_multiplier (bool): If True, multiplies current by sqrt(2).
        """
        current_map = {0.1: 0, 0.2: 1, 0.5: 2, 1.0: 3, 2.0: 4, 
                       5.0: 5, 10.0: 6, 20.0: 7, 50.0: 8}
        if current_ma in current_map:
            code = current_map[current_ma]
            if sqrt2_multiplier:
                code += 10 # Codes 10-18 add sqrt(2) multiplier
            self.bridge.write(f"C{code}")
            time.sleep(1.5)
            status = "ON" if sqrt2_multiplier else "OFF"
            print(f"[INFO] Current set to {current_ma} mA (sqrt(2) mode: {status}).")
        else:
            raise ValueError("Invalid current.")

    def set_gain(self, gain_value):
        """
        Sets the measurement gain of the bridge (G command).
        
        SAFETY FEATURE: This command is blocked if the meter is set to 
        Quadrature mode, as changing gain in this state is invalid. Use 
        the REF command instead.
        
        Instead of hardware codes, this function accepts the actual numerical
        gain value and translates it to the proper hardware code (0 to 7).
        
        Args:
            gain_value (int): Actual gain multiplier. 
                              Allowed values: 1, 10, 100, 1000, 10000, 
                                              100000, 1000000, 10000000.
        """
        
        # Sefety lock for Quadrature mode (MET = 1)
        if self._meter_mode == 1:
            raise RuntimeError(
                "[ERROR] Gain (G) command is inactive when Meter is in Quadrature "
                "mode. Please use the 'set_reference' (REF) command instead."
            )
            
        gain_map = {
            1: 0,
            10: 1,
            100: 2,
            1000: 3,
            10000: 4,
            100000: 5,
            1000000: 6,
            10000000: 7
        }
        
        if gain_value in gain_map:
            code = gain_map[gain_value]
            self.bridge.write(f"G{code}")
            print(f"[INFO] Gain set to {gain_value}x (Hardware code: {code}).")
            time.sleep(0.5) # Short pause to allow relays to switch
        else:
            raise ValueError(f"Invalid gain value. Allowed values: {list(gain_map.keys())}")

    def set_source_impedance(self, ohms):
        """
        Sets the source impedance (SRC command).
        
        Args:
            ohms (int): Impedance in Ohms. Allowed: 1, 10, 100.
        """
        src_map = {1: 0, 10: 1, 100: 2}
        if ohms in src_map:
            self.bridge.write(f"SRC{src_map[ohms]}")
            print(f"[INFO] Source impedance set to {ohms} Ohm.")
        else:
            raise ValueError("Invalid impedance.")

    def set_frequency(self, mode):
        """
        Sets the carrier frequency (FRQ command).
        Accepts both integer codes and readable strings.
        
        Args:
            mode (int/str):
                0 or 'low'  = Low frequency
                1 or 'high' = High frequency (Default)
        """
        freq_map = {
            0: 0, 'low': 0,
            1: 1, 'high': 1
        }
        
        # Unification of input (np. 'LOW', 'Low', 'low')
        if isinstance(mode, str):
            mode = mode.lower()
            
        if mode in freq_map:
            code = freq_map[mode]
            self.bridge.write(f"FRQ{code}")
            desc = "Low frequency" if code == 0 else "High frequency"
            print(f"[INFO] Carrier frequency set to: {desc} (FRQ{code}).")
        else:
            raise ValueError("Invalid frequency. Allowed values: 0, 1, 'low', 'high'.")

    def set_meter_mode(self, mode):
        """
        Selects the analog meter mode (MET command).
        Accepts both integer codes and readable strings.
        
        Args:
            mode (int/str):
                0 or 'off'  = Out of balance reading (Default)
                1 or 'quad' = Quadrature reading (Disables Gain adjustments)
                2 or 'res'  = Residual reading
        """
        meter_map = {
            0: 0, 'off': 0, 'out': 0,
            1: 1, 'quad': 1, 'quadrature': 1,
            2: 2, 'res': 2, 'residual': 2
        }
        
        if isinstance(mode, str):
            mode = mode.lower()
            
        if mode in meter_map:
            code = meter_map[mode]
            self.bridge.write(f"MET{code}")
            
            # Save the status in class to lock command Gain in mode Quad
            self._meter_mode = code
            
            desc = ["Out of balance", "Quadrature", "Residual"][code]
            print(f"[INFO] Meter mode set to: {desc} (MET{code}).")
            
            if code == 1:
                print("[WARNING] Quadrature mode active. Gain (G) changes are now DISABLED.")
        else:
            raise ValueError("Invalid meter mode. Allowed values: 0, 1, 2, 'off', 'quad', 'res'.")

    def set_reference(self, code):
        """
        Selects the reference resistor adjustment (REF command).
        This command is specifically used when adjusting parameters in 
        Quadrature mode, where normal Gain adjustments are disabled.
        
        Args:
            code (int): Reference selection code.
        """
        self.bridge.write(f"REF{code}")
        print(f"[INFO] Reference set to code {code}.")  

    # =========================================================================
    # PRESET COMMANDS (P, PA)
    # =========================================================================

    def preset_ratio(self, value):
        """
        Sends a preset ratio value to the bridge (P command).
        Automatically sets the bridge into manual balance mode.
        
        Args:
            value (str/float): The ratio value to preset (e.g., "1.0000000").
        """
        self.bridge.write(f"P{value}")
        print(f"[INFO] Preset ratio set to {value} (Switched to Manual mode).")

    def preset_auto(self):
        """
        Presets the bridge with the current ratio in auto mode, 
        then switches to manual mode (PA command).
        """
        self.bridge.write("PA")
        print("[INFO] Preset Auto (PA) executed. Bridge is now in Manual mode.")

    # =========================================================================
    # DIAGNOSTIC & ADVANCED COMMANDS (CHK, DAC, SRM, Q, ?)
    # =========================================================================

    def set_dac(self, code):
        """
        Sets the analogue output range for the DAC (DAC command).
        
        Args:
            code (int): Range selection code from 0 to 3.
                0 = range digit 3 to digit 5
                1 = range digit 4 to digit 6
                2 = range digit 5 to digit 7 (Default)
                3 = range extended
        """
        if code in [0, 1, 2, 3]:
            self.bridge.write(f"DAC{code}")
            print(f"[INFO] DAC output range set to code {code}.")
        else:
            raise ValueError("Invalid DAC code. Allowed codes: 0, 1, 2, 3.")

    def set_service_request_mask(self, mask):
        """
        Sets the Service Request Mask (SRM command) for GPIB interrupts.
        
        This instruction allows the user to set a mask for the GPIB service 
        request function. Setting a mask causes a request service function to be 
        generated whenever the bridge condition corresponds with the mask.
        
        The parameter 'mask' is a number between 0 and 255 forming a bit-wise mask.
        Bit functions:
        - Bit 7 (Val: 128) : Data available (requests service whenever ratio is updated).
        - Bit 6 (Val:  64) : Request Service bit (indicates F18 was the source of interrupt).
        - Bit 5 (Val:  32) : Not balanced (requests service even if F18 is not balanced).
        - Bit 4 (Val:  16) : Balanced (requests service when the F18 is balanced).
        - Bit 3 (Val:   8) : Overload error (requests service on bridge overload error).
        - Bit 2 (Val:   4) : Not used.
        - Bit 1 (Val:   2) : Not used.
        - Bit 0 (Val:   1) : Not used.
        
        Initial value: 0 (no mask set).
        
        Example: 
            mask=128 sets Bit 7 (alert on balance cycle completion).
            
        Args:
            mask (int): A number between 0 and 255.
        """
        if 0 <= mask <= 255:
            self.bridge.write(f"SRM{mask}")
            print(f"[INFO] Service Request Mask (SRM) set to {mask}.")
        else:
            raise ValueError("SRM mask must be between 0 and 255.")

    def get_status_dump(self):
        """
        Requests the full 72-byte status dump from the instrument (Q command).
        Provides a positive indication that commands sent or parameters changed
        have been acted upon.
        
        How to read this string:
        The returned data is a fixed-length string of 72 bytes (including CR and LF).
        It does not use commas; instead, the position (index) of each character 
        in the string corresponds to a specific internal setting of the bridge 
        (e.g., byte 0 might be Gain code, byte 1 Current code, etc., depending on 
        the exact table in the F18 operator's manual).
        
        You can extract specific parameters in Python by string slicing, for example:
        current_code = status_data[1]
        
        Returns:
            str: The full 72-byte raw status string.
        """
        try:
            status_data = self.bridge.query("Q").strip()
            print(f"[INFO] Status Dump (Q): {status_data}")
            return status_data
        except Exception as e:
            print(f"[ERROR] Failed to fetch status dump: {e}")
            return None

    def get_measurement(self):
        """
        Queries the bridge for the current reading (?) and parses the status.
        
        Returns:
            dict: Parsed numerical ratio, status code, description, and validity flag.
        """
        raw_data = ""
        try:
            raw_data = self.bridge.query("?").strip()
            if not raw_data:
                return None
                
            status_letter = raw_data[-1].upper()
            ratio_number = float(raw_data[:-1])
            
            status_map = {'B': 'Balanced', 'L': 'Low', 'H': 'High', 'E': 'Error'}
            status_desc = status_map.get(status_letter, f"Unknown ({status_letter})")
            
            return {
                'ratio': ratio_number,
                'status_code': status_letter,
                'status_desc': status_desc,
                'is_valid': status_letter == 'B'
            }
        except Exception as e:
            print(f"[WARNING] Data parsing error: {e}. Raw data: '{raw_data}'")
            return None

    def close(self):
        """Closes the VISA session."""
        self.bridge.close()
        self.rm.close()
        print("[INFO] Connection closed.")
        
    @staticmethod
    def scan_for_bridge():
        """
        Scans GPIB addresses from 0 to 31 to find the ASL F18 bridge.
        Returns the valid resource string or None.
        """
        rm = pyvisa.ResourceManager()
        print("[SCAN] Searching for F18 bridge on GPIB0...")
        for addr in range(32):
            resource = f"GPIB0::{addr}::INSTR"
            try:
                # Try to open and send a basic ID or Online command
                instr = rm.open_resource(resource)
                instr.timeout = 500
                # We try to query something or just check if it exists
                # Most ASL bridges respond to 'ONL' or '?'
                instr.write("ONL") 
                print(f"[SCAN] Found device at {resource}!")
                instr.close()
                return resource
            except:
                continue
        return None