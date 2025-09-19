#!/usr/bin/env python3
"""Visual demonstration of the new DS launcher workflow"""


def demo_workflow():
    print("🚀 NEW DS LAUNCHER WORKFLOW DEMONSTRATION")
    print("=" * 60)

    print("\n1️⃣ You run: DS_Netio_pdu.bat 1_V0")
    print("   Output:")
    print("   =====================================================")
    print("   Starting DS_Netio_pdu Device Server")
    print("   Instance: 1_V0")
    print("   Environment: pyconlyse39")
    print("   =====================================================")
    print("   ")
    print("   Starting in new visible terminal window...")
    print("   Terminal title: DS_Netio_pdu [1_V0]")
    print("   ")
    print(
        "   A separate Control window will open. Type STOP there to terminate this DS."
    )
    print("   ")
    print("   Device server started in separate terminal window!")
    print("   You can monitor and control it from the terminal titled:")
    print('   "DS_Netio_pdu [1_V0]"')

    print("\n2️⃣ Two Windows Open:")
    print(
        "┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐"
    )
    print(
        "│ DS_Netio_pdu [1_V0]                 │  │ Control - DS_Netio_pdu [1_V0]       │"
    )
    print(
        "├─────────────────────────────────────┤  ├─────────────────────────────────────┤"
    )
    print(
        "│ Starting DS_Netio_pdu device server │  │ Control for DS_Netio_pdu [1_V0].    │"
    )
    print(
        "│ Archive disabled: Using mock archive│  │ Type STOP to terminate this device  │"
    )
    print(
        "│ Device 1_V0 NetioPDU was found.     │  │ server, or EXIT to close control.   │"
    )
    print(
        "│ Ready to accept requests            │  │ Command (STOP/EXIT): _              │"
    )
    print(
        "│                                     │  │                                     │"
    )
    print(
        "│ [LOGS ONLY - NO USER INPUT]         │  │ [USER COMMANDS HERE]                │"
    )
    print(
        "└─────────────────────────────────────┘  └─────────────────────────────────────┘"
    )

    print("\n3️⃣ With Debug Timing Enabled, DS Window Shows:")
    print("   Starting DS_Netio_pdu device server...")
    print("   Archive disabled: Using mock archive (no connection attempt)")
    print("   === INIT TIMING (ms) ===")
    print("   internal_time_started: 15.2 ms (t=15.2)")
    print("   tango_Device.init_device: 234.7 ms (t=249.9)")
    print("   parameters_parsed: 12.1 ms (t=262.0)")
    print("   archive_init: 3.4 ms (t=265.4)")
    print("   find_device: 1847.8 ms (t=2113.2)  ← SLOW STEP!")
    print("   post_find_device: 2.1 ms (t=2115.3)")
    print("   Total init: 2115.3 ms")
    print("   Device 1_V0 NetioPDU was found.")
    print("   Ready to accept requests")

    print("\n4️⃣ To Stop DS, Control Window:")
    print("   Command (STOP/EXIT): STOP")
    print("   Sent stop to DS_Netio_pdu [1_V0].")
    print("   [DS window closes immediately]")

    print("\n5️⃣ Commands Available from Any Running DS:")
    print("   ┌─────────────────────────────────────────────────────────┐")
    print("   │ Tango Command              │ Purpose                    │")
    print("   ├─────────────────────────────────────────────────────────┤")
    print("   │ list_global_variables()    │ Show current settings      │")
    print("   │ set_global_variable(['DEBUG_INIT_TIMING','true'])       │")
    print("   │ set_global_variable(['DEBUG_TIMING_THRESHOLD_MS','5'])  │")
    print("   │ save_global_variables()    │ Save to JSON file          │")
    print("   │ reload_global_variables()  │ Reload from JSON file      │")
    print("   │ get_global_config_path()   │ Show config file path      │")
    print("   └─────────────────────────────────────────────────────────┘")

    print("\n6️⃣ Benefits:")
    print("   ✅ Clean separation: DS logs vs user commands")
    print("   ✅ Easy termination: Type STOP instead of Ctrl+C hunting")
    print("   ✅ Precise timing: See exactly which init step is slow")
    print("   ✅ Global control: Enable debugging for all DS at once")
    print("   ✅ Persistent settings: Save/reload from JSON file")

    print("\n📁 Config File Location:")
    print("   C:\\dev\\pyconlyse\\DeviceServers\\global_settings.json")

    print("\n🎯 Ready to Use:")
    print("   1. Run: .\\DS_Netio_pdu.bat 1_V0")
    print("   2. Use Control window to type STOP when done")
    print("   3. Enable debug timing from any DS to see init breakdown")


if __name__ == "__main__":
    demo_workflow()
