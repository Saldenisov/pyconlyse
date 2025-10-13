from tango import Database, DbDevInfo

# Register iTest PSU device(s) in Tango DB
# Adjust the "devices" list to add more entries if needed.

# Example entry fields:
#   domain/family - Tango path prefix, e.g. "manip/V0"
#   member        - Tango member part, e.g. "iTest_PSU"
#   short_name    - Short ID appended to the server instance name
#   host          - Instrument IP address
#   port          - Instrument TCP port (default SCPI: 5025)
#   config_path   - Path to the JSON config with start_current
#   eol           - Line terminator: "\n", "\r\n", or "\r"
#   enable_output - Whether to enable output at init
#   start_current - Optional starting current (overridden by ConfigPath if set)

devices = [
    {
        "domain_family": "ELYSE/pdu",
        "member": "iTest",
        "short_name": "iTest",
        "host": "10.20.30.24",
        "port": 5025,
        "config_path": r"C:\\dev\\pyconlyse\\DeviceServers\\power\\iTest\\itest_psu_config.json",
        "eol": "\n",
        "enable_output": False,
        "start_current": 0.0,
    }
]


def main() -> None:
    db = Database()
    i = 1
    for d in devices:
        dev_info = DbDevInfo()
        dev_name = f"{d['domain_family']}/{d['member']}"
        dev_info.name = dev_name
        dev_info._class = "DS_iTest_PSU"
        dev_info.server = f"DS_itest_psu/{i}_{d['short_name']}"
        db.add_device(dev_info)
        props = {
            "Host": d["host"],
            "Port": d["port"],
            "ConfigPath": d["config_path"],
            "EOL": d["eol"],
            "EnableOutputOnInit": d["enable_output"],
            "StartCurrent": d["start_current"],
        }
        db.put_device_property(dev_name, props)
        i += 1


if __name__ == "__main__":
    main()
