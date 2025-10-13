from tango import Database

def main():
    db = Database()
    server = "itest_psu_device/1_iTest"

    # Find devices attached to the old server
    try:
        devices = db.get_device_name(server, "*")
    except Exception:
        devices = []

    for dn in devices:
        try:
            db.delete_device(dn)
            print(f"Deleted device: {dn}")
        except Exception as e:
            print(f"WARN: delete_device({dn}) failed: {e}")

    # Remove server entry
    try:
        db.delete_server_info(server)
        print(f"Deleted server info: {server}")
    except Exception as e:
        print(f"WARN: delete_server_info failed: {e}")
        try:
            db.delete_server(server)
            print(f"Deleted server: {server}")
        except Exception as e2:
            print(f"WARN: delete_server failed: {e2}")


if __name__ == "__main__":
    main()
