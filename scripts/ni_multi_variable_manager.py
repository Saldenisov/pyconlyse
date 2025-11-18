"""
Multi-Variable Manager for LabVIEW Shared Variables

Handles multiple variables from ni.var.psp://eureka/SUPERVISION efficiently
After installing NI software, this will read all variables in batch
"""

import sys
import time
from datetime import datetime

try:
    import clr
    print("✓ pythonnet loaded")
    
    try:
        clr.AddReference("NationalInstruments.NetworkVariable")
        clr.AddReference("NationalInstruments.Common")
        
        from NationalInstruments.NetworkVariable import (
            NetworkVariableBufferedSubscriber,
            NetworkVariableBufferedWriter
        )
        
        print("✓ NI .NET assemblies loaded")
        NI_AVAILABLE = True
        
    except Exception as e:
        print(f"✗ NI assemblies not available: {e}")
        print("Install NI LabVIEW Runtime first")
        NI_AVAILABLE = False
        
except ImportError:
    print("✗ pythonnet not installed: pip install pythonnet")
    NI_AVAILABLE = False


class SupervisionVariableManager:
    """
    Manager for multiple variables in the SUPERVISION library
    
    Host: eureka (10.20.30.10)
    Library: SUPERVISION
    Variables: 20+ variables (add them below)
    """
    
    def __init__(self, host="eureka", library="SUPERVISION"):
        self.host = host
        self.library = library
        self.subscribers = {}
        self.writers = {}
        
        # TODO: Add your variable names here
        # You can see them in LabVIEW 2020 under ni.var.psp://eureka/SUPERVISION
        self.variable_names = [
            "C1011NI6602",  # Example - add more below
            # "C1011NI6603",
            # "C1011NI6604",
            # Add all 20+ variable names here
        ]
    
    def add_variable(self, variable_name):
        """Add a variable to the monitoring list"""
        if variable_name not in self.variable_names:
            self.variable_names.append(variable_name)
            print(f"Added variable: {variable_name}")
    
    def set_variables(self, variable_list):
        """Set the complete list of variables to monitor"""
        self.variable_names = variable_list
        print(f"Set {len(variable_list)} variables")
    
    def read_variable(self, variable_name):
        """Read a single variable"""
        if not NI_AVAILABLE:
            print("NI assemblies not available")
            return None
        
        path = f"\\\\{self.host}\\{self.library}\\{variable_name}"
        
        try:
            # Reuse subscriber if exists
            if path not in self.subscribers:
                subscriber = NetworkVariableBufferedSubscriber(path)
                subscriber.Connect()
                self.subscribers[path] = subscriber
            else:
                subscriber = self.subscribers[path]
            
            data = subscriber.ReadData()
            value = data.GetValue()
            return value
            
        except Exception as e:
            print(f"Error reading {variable_name}: {e}")
            return None
    
    def read_all_variables(self):
        """
        Read all variables in the list
        
        Returns:
            dict: {variable_name: value}
        """
        results = {}
        
        print(f"Reading {len(self.variable_names)} variables from {self.library}...")
        
        for var_name in self.variable_names:
            value = self.read_variable(var_name)
            results[var_name] = value
            print(f"  {var_name}: {value}")
        
        return results
    
    def write_variable(self, variable_name, value):
        """Write to a single variable"""
        if not NI_AVAILABLE:
            print("NI assemblies not available")
            return False
        
        path = f"\\\\{self.host}\\{self.library}\\{variable_name}"
        
        try:
            if path not in self.writers:
                writer = NetworkVariableBufferedWriter(path)
                writer.Connect()
                self.writers[path] = writer
            else:
                writer = self.writers[path]
            
            writer.WriteData(value)
            print(f"✓ Wrote {value} to {variable_name}")
            return True
            
        except Exception as e:
            print(f"✗ Error writing {variable_name}: {e}")
            return False
    
    def monitor_continuous(self, interval=1.0, duration=None):
        """
        Continuously monitor all variables
        
        Args:
            interval: Seconds between reads (default: 1.0)
            duration: Total duration in seconds (None = infinite)
        """
        if not NI_AVAILABLE:
            print("NI assemblies not available")
            return
        
        print(f"\nMonitoring {len(self.variable_names)} variables")
        print(f"Interval: {interval}s")
        print("Press Ctrl+C to stop\n")
        print("-" * 80)
        
        start_time = time.time()
        
        try:
            while True:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"\n[{timestamp}]")
                
                results = self.read_all_variables()
                
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    print(f"\nMonitoring completed ({duration}s)")
                    break
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
    
    def export_to_csv(self, filename="supervision_variables.csv", duration=60, interval=1.0):
        """
        Log variable values to CSV file
        
        Args:
            filename: Output CSV filename
            duration: Recording duration in seconds
            interval: Sampling interval in seconds
        """
        if not NI_AVAILABLE:
            print("NI assemblies not available")
            return
        
        import csv
        
        print(f"Logging to {filename} for {duration}s...")
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            header = ['timestamp'] + self.variable_names
            writer.writerow(header)
            
            start_time = time.time()
            
            try:
                while (time.time() - start_time) < duration:
                    timestamp = datetime.now().isoformat()
                    results = self.read_all_variables()
                    
                    row = [timestamp] + [results.get(var) for var in self.variable_names]
                    writer.writerow(row)
                    
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                print("\nLogging stopped by user")
        
        print(f"✓ Data saved to {filename}")
    
    def get_variable_url(self, variable_name):
        """Get the full PSP URL for a variable"""
        return f"ni.var.psp://{self.host}/{self.library}/{variable_name}"
    
    def list_variables(self):
        """List all configured variables"""
        print(f"\nConfigured variables in {self.library} ({len(self.variable_names)}):")
        print("-" * 60)
        for i, var in enumerate(self.variable_names, 1):
            url = self.get_variable_url(var)
            print(f"{i:2}. {var}")
            print(f"    {url}")
    
    def close(self):
        """Close all connections"""
        for sub in self.subscribers.values():
            try:
                sub.Disconnect()
            except:
                pass
        
        for writer in self.writers.values():
            try:
                writer.Disconnect()
            except:
                pass
        
        print("✓ All connections closed")


def setup_wizard():
    """Interactive setup to add variable names"""
    print("=" * 70)
    print("SUPERVISION Variable Setup Wizard")
    print("=" * 70)
    print("\nYou mentioned there are 20+ variables in ni.var.psp://eureka/SUPERVISION")
    print("\nPlease provide the variable names. Options:")
    print("  1. Enter names one by one (type 'done' when finished)")
    print("  2. Paste comma-separated list")
    print("  3. Load from file")
    
    choice = input("\nChoice (1/2/3): ").strip()
    
    variables = []
    
    if choice == "1":
        print("\nEnter variable names (type 'done' when finished):")
        while True:
            var = input(f"  Variable {len(variables)+1}: ").strip()
            if var.lower() == 'done':
                break
            if var:
                variables.append(var)
    
    elif choice == "2":
        var_string = input("\nPaste comma-separated names: ").strip()
        variables = [v.strip() for v in var_string.split(',') if v.strip()]
    
    elif choice == "3":
        filename = input("File path: ").strip()
        try:
            with open(filename, 'r') as f:
                variables = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error reading file: {e}")
    
    if variables:
        print(f"\n✓ Loaded {len(variables)} variables:")
        for v in variables:
            print(f"  - {v}")
        
        # Save to Python file
        save = input("\nSave to variable_list.py? (y/n): ").strip().lower()
        if save == 'y':
            with open("variable_list.py", 'w') as f:
                f.write("# SUPERVISION Library Variables\n")
                f.write("# Host: eureka (10.20.30.10)\n\n")
                f.write("SUPERVISION_VARIABLES = [\n")
                for v in variables:
                    f.write(f"    '{v}',\n")
                f.write("]\n")
            print("✓ Saved to variable_list.py")
    
    return variables


def main():
    print("=" * 70)
    print("Multi-Variable Manager for SUPERVISION Library")
    print("=" * 70)
    
    if not NI_AVAILABLE:
        print("\n⚠ NI assemblies not available")
        print("Install NI LabVIEW Runtime first, then run this script\n")
        
        # Still allow setup
        print("You can still set up variable names for later use:")
        setup_wizard()
        return
    
    manager = SupervisionVariableManager()
    
    # Check if variable_list.py exists
    try:
        from variable_list import SUPERVISION_VARIABLES
        manager.set_variables(SUPERVISION_VARIABLES)
        print(f"✓ Loaded {len(SUPERVISION_VARIABLES)} variables from variable_list.py")
    except ImportError:
        print("\nNo variable_list.py found")
        print("Current variables:", manager.variable_names)
        
        setup = input("\nRun setup wizard to add variables? (y/n): ").strip().lower()
        if setup == 'y':
            variables = setup_wizard()
            if variables:
                manager.set_variables(variables)
    
    # Menu
    while True:
        print("\n" + "=" * 70)
        print("Options:")
        print("  1. List configured variables")
        print("  2. Read all variables once")
        print("  3. Monitor continuously")
        print("  4. Export to CSV")
        print("  5. Read single variable")
        print("  6. Write to variable")
        print("  7. Add/setup variables")
        print("  0. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == "1":
            manager.list_variables()
        
        elif choice == "2":
            results = manager.read_all_variables()
        
        elif choice == "3":
            interval = float(input("Interval (seconds, default 1.0): ") or "1.0")
            manager.monitor_continuous(interval=interval)
        
        elif choice == "4":
            filename = input("Filename (default: supervision_variables.csv): ").strip() or "supervision_variables.csv"
            duration = int(input("Duration (seconds, default 60): ") or "60")
            interval = float(input("Interval (seconds, default 1.0): ") or "1.0")
            manager.export_to_csv(filename, duration, interval)
        
        elif choice == "5":
            var_name = input("Variable name: ").strip()
            value = manager.read_variable(var_name)
            print(f"\n{var_name} = {value}")
        
        elif choice == "6":
            var_name = input("Variable name: ").strip()
            value = input("Value: ").strip()
            # Try to convert to number
            try:
                value = float(value)
            except:
                pass
            manager.write_variable(var_name, value)
        
        elif choice == "7":
            variables = setup_wizard()
            if variables:
                manager.set_variables(variables)
        
        elif choice == "0":
            manager.close()
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
