#!/usr/bin/env python3
"""
Discovery script for iTest PSU cards.

This script:
1. Connects to the iTest instrument via SCPI
2. Discovers available cards/slots using INST:LIST?
3. Registers each discovered card as a separate Tango device in the database
4. Sets up proper device properties for each card

Usage: python discover_and_register_cards.py [--host IP] [--port PORT]
"""

import sys
import json
import argparse
from typing import List, Dict, Any
from pathlib import Path

# Add the project root to path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.append(str(project_root))

from tango import Database, DbDevInfo
from DeviceServers.power.iTest.scpi_client import SCPISocket, SCPIError


def discover_cards(host: str, port: int = 5025, timeout: float = 5.0) -> List[Dict[str, Any]]:
    """
    Connect to instrument and discover available cards/slots.
    
    Returns:
        List of card info dictionaries with slot, model, and derived name
    """
    print(f"Connecting to {host}:{port}...")
    
    try:
        scpi = SCPISocket(host, port, timeout=timeout)
        scpi.connect()
        
        # Get instrument identification
        try:
            idn = scpi.idn()
            print(f"Connected to: {idn}")
        except Exception as e:
            print(f"Warning: Could not get *IDN?: {e}")
            idn = "Unknown"
        
        # Discover cards using INST:LIST?
        print("Discovering cards with INST:LIST?...")
        try:
            raw_list = scpi.query("INST:LIST?")
            print(f"Raw INST:LIST? response: {raw_list}")
        except Exception as e:
            print(f"Error: INST:LIST? failed: {e}")
            print("This instrument may not support multi-slot discovery.")
            print("Falling back to single channel assumption...")
            return [{
                "slot": 1,
                "model": "Unknown",
                "name": "slot_1",
                "idn": idn
            }]
        
        # Parse the response
        cards = []
        for entry in str(raw_list).split(";"):
            entry = entry.strip()
            if not entry:
                continue
                
            try:
                # Expected format: "slot,model" like "1,IT6432" or "7,IT6432"
                parts = entry.split(",", 1)
                if len(parts) != 2:
                    print(f"Warning: Unexpected entry format '{entry}', skipping")
                    continue
                    
                slot_str, model_str = parts
                slot = int(slot_str.strip())
                model = model_str.strip()
                
                # Create a meaningful name
                name = f"slot_{slot}_model_{model}"
                
                cards.append({
                    "slot": slot,
                    "model": model, 
                    "name": name,
                    "idn": idn
                })
                
                print(f"Found: Slot {slot}, Model {model}")
                
            except ValueError as e:
                print(f"Warning: Could not parse slot number from '{entry}': {e}")
                continue
            except Exception as e:
                print(f"Warning: Error parsing entry '{entry}': {e}")
                continue
        
        scpi.close()
        
        if not cards:
            print("No cards discovered via INST:LIST?, using fallback single card")
            cards = [{
                "slot": 1,
                "model": "Unknown",
                "name": "slot_1",
                "idn": idn
            }]
        
        print(f"Discovery complete. Found {len(cards)} card(s)")
        return cards
        
    except Exception as e:
        print(f"Error during discovery: {e}")
        raise


def register_cards_in_tango_db(cards: List[Dict[str, Any]], host: str, port: int = 5025):
    """
    Register discovered cards in Tango database as separate devices.
    """
    print(f"\nRegistering {len(cards)} cards in Tango database...")
    
    db = Database()
    
    # Base configuration
    base_domain_family = "ELYSE/pdu"
    server_class = "DS_iTest_PSU"
    
    for i, card in enumerate(cards, 1):
        slot = card["slot"]
        model = card["model"]
        name = card["name"]
        
        # Create device name: ELYSE/pdu/iTest_slot_N
        device_name = f"{base_domain_family}/iTest_slot_{slot}"
        
        print(f"Registering device: {device_name}")
        
        # Create device info
        dev_info = DbDevInfo()
        dev_info.name = device_name
        dev_info._class = server_class
        dev_info.server = f"DS_itest_psu/{i}_{name}"
        
        try:
            # Add device to database
            db.add_device(dev_info)
            print(f"  Added device: {device_name}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  Device {device_name} already exists, updating properties...")
            else:
                print(f"  Error adding device {device_name}: {e}")
                continue
        
        # Set device properties
        props = {
            "Host": host,
            "Port": port,
            "EOL": "\\n",
            "EnableOutputOnInit": False,
            "StartCurrent": 0.0,
            "UseDiscovery": True,  # Enable discovery for this device
            "SafeCurrentMin": -5.0,
            "SafeCurrentMax": 5.0,
            "ChannelsPerRack": 1,  # Each device represents one card/slot
            # Store slot and model info as properties for reference
            "SlotNumber": slot,
            "CardModel": model,
        }
        
        try:
            db.put_device_property(device_name, props)
            print(f"  Set properties for: {device_name}")
            print(f"    Slot: {slot}, Model: {model}")
        except Exception as e:
            print(f"  Error setting properties for {device_name}: {e}")
    
    print(f"\nDatabase registration complete!")
    print(f"You can now start device servers for the registered devices.")


def create_device_list_summary(cards: List[Dict[str, Any]]) -> None:
    """Create a summary file of discovered devices."""
    summary_file = Path(__file__).parent / "discovered_devices.json"
    
    summary = {
        "discovery_timestamp": __import__("datetime").datetime.now().isoformat(),
        "total_cards": len(cards),
        "cards": cards,
        "tango_devices": [f"ELYSE/pdu/iTest_slot_{card['slot']}" for card in cards]
    }
    
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nDiscovery summary saved to: {summary_file}")
    print("\nDiscovered Tango devices:")
    for dev_name in summary["tango_devices"]:
        print(f"  {dev_name}")


def main():
    parser = argparse.ArgumentParser(description="Discover and register iTest PSU cards")
    parser.add_argument("--host", default="10.20.30.24", 
                       help="Instrument IP address (default: 10.20.30.24)")
    parser.add_argument("--port", type=int, default=5025,
                       help="SCPI port (default: 5025)")
    parser.add_argument("--timeout", type=float, default=5.0,
                       help="SCPI timeout in seconds (default: 5.0)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Discover cards but don't register in Tango DB")
    
    args = parser.parse_args()
    
    try:
        # Step 1: Discover cards
        cards = discover_cards(args.host, args.port, args.timeout)
        
        if not cards:
            print("No cards discovered!")
            return 1
        
        # Step 2: Create summary
        create_device_list_summary(cards)
        
        if args.dry_run:
            print("\n--dry-run specified, skipping Tango database registration")
            print("Run without --dry-run to actually register the devices")
            return 0
        
        # Step 3: Register in Tango database
        register_cards_in_tango_db(cards, args.host, args.port)
        
        print("\n" + "="*50)
        print("SUCCESS: Discovery and registration complete!")
        print("="*50)
        print("\nNext steps:")
        print("1. Start the device servers using Astor or the batch files")
        print("2. Run the client to see the discovered cards:")
        print(f"   python DeviceServers/power/iTest/DS_iTest_PSU_client.py ELYSE/pdu/iTest_slot_1")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())