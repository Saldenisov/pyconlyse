"""
OWIS PS90 Ethernet Communication Test
Connect to PS90 controller and send ASCII commands
"""
import socket
import time

# Connection settings
HOST = "10.20.30.134"
PORT = 8777
TIMEOUT = 5  # seconds

def send_command(sock: socket.socket, command: str) -> str:
    """Send ASCII command and read response."""
    # OWIS commands are ASCII, typically terminated with CR or CR+LF
    cmd_bytes = (command + "\r").encode("ascii")
    print(f"Sending: {command!r}")
    sock.sendall(cmd_bytes)
    
    time.sleep(0.1)  # Small delay for response
    
    # Read response
    try:
        response = sock.recv(1024).decode("ascii", errors="replace")
        print(f"Response: {response!r}")
        return response
    except socket.timeout:
        print("No response (timeout)")
        return ""

def main():
    print(f"Connecting to OWIS PS90 at {HOST}:{PORT}...")
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TIMEOUT)
            sock.connect((HOST, PORT))
            print("Connected!\n")
            
            # Test basic queries
            commands = [
                "?SERNUM",    # Query serial number
                "?VERSION",   # Query firmware version
                "INIT",       # Initialize
            ]
            
            for cmd in commands:
                send_command(sock, cmd)
                print()
            
            # Interactive mode
            print("\n--- Interactive Mode (type 'quit' to exit) ---")
            while True:
                user_cmd = input("Command> ").strip()
                if user_cmd.lower() == "quit":
                    break
                if user_cmd:
                    send_command(sock, user_cmd)
                    
    except socket.timeout:
        print(f"Connection timeout - could not connect to {HOST}:{PORT}")
    except ConnectionRefusedError:
        print(f"Connection refused - is the controller listening on port {PORT}?")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
