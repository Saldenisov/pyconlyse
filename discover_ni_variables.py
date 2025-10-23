import socket
import struct
import select

def discover_ni_variables(target_host="10.20.30.10", timeout=5):
    """
    Discover LabVIEW shared variables using mDNS/NI-PSP protocol
    """
    MCAST_GRP = '224.0.0.251'  # mDNS multicast group
    MCAST_PORT = 5353
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind to mDNS port
    try:
        sock.bind(('', MCAST_PORT))
    except OSError as e:
        print(f"Warning: Could not bind to port {MCAST_PORT}: {e}")
        print("Trying alternative discovery method...")
        return discover_ni_direct(target_host)
    
    # Join multicast group
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    # Send mDNS query for NI services
    query = build_mdns_query()
    sock.sendto(query, (MCAST_GRP, MCAST_PORT))
    
    print(f"Searching for NI variables on {target_host}...")
    print("Listening for mDNS responses...\n")
    
    discovered = []
    sock.settimeout(timeout)
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                if addr[0] == target_host or target_host == "0.0.0.0":
                    print(f"Response from {addr[0]}:{addr[1]}")
                    parsed = parse_mdns_response(data)
                    if parsed:
                        discovered.append((addr[0], parsed))
                        print(f"  Found: {parsed}\n")
            except socket.timeout:
                break
    except KeyboardInterrupt:
        print("\nSearch interrupted by user")
    finally:
        sock.close()
    
    return discovered


def build_mdns_query():
    """Build mDNS query for _ni._tcp.local and _ni-psp._tcp.local services"""
    query = bytearray()
    
    # Transaction ID
    query.extend(b'\x00\x00')
    # Flags (standard query)
    query.extend(b'\x00\x00')
    # Questions
    query.extend(b'\x00\x01')
    # Answer RRs
    query.extend(b'\x00\x00')
    # Authority RRs
    query.extend(b'\x00\x00')
    # Additional RRs
    query.extend(b'\x00\x00')
    
    # Query: _ni._tcp.local PTR
    for label in ['_ni', '_tcp', 'local']:
        query.append(len(label))
        query.extend(label.encode('ascii'))
    query.append(0)  # End of name
    
    # Type PTR, Class IN
    query.extend(b'\x00\x0c\x00\x01')
    
    return bytes(query)


def parse_mdns_response(data):
    """Parse mDNS response for NI service information"""
    try:
        # Simple parsing - look for _ni service names
        data_str = data.decode('latin-1', errors='ignore')
        if '_ni' in data_str or 'National Instruments' in data_str:
            return data_str[:200]  # Return first 200 chars for inspection
    except:
        pass
    return None


def discover_ni_direct(target_host="10.20.30.10"):
    """
    Direct connection to NI Variable Engine ports
    """
    print(f"\nDirect port scanning on {target_host}...")
    
    # Known NI ports
    ni_ports = {
        2343: "NI Variable Engine",
        3580: "NI PSP Server",
        5353: "mDNS",
        80: "HTTP (Variable Web Server)",
        443: "HTTPS (Variable Web Server)"
    }
    
    discovered = []
    
    for port, service in ni_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((target_host, port))
        
        if result == 0:
            print(f"✓ {service} (port {port}) - OPEN")
            discovered.append((target_host, port, service))
            
            # Try to get banner/info
            if port in [80, 443]:
                try:
                    http_req = b"GET /ni-vars HTTP/1.1\r\nHost: " + target_host.encode() + b"\r\n\r\n"
                    sock.send(http_req)
                    response = sock.recv(1024)
                    print(f"  Response: {response[:100]}")
                except:
                    pass
        else:
            print(f"✗ {service} (port {port}) - closed")
        
        sock.close()
    
    return discovered


def try_http_variable_list(target_host="10.20.30.10"):
    """
    Try to fetch variable list via HTTP API
    """
    print(f"\nAttempting HTTP API access on {target_host}...")
    
    try:
        import urllib.request
        
        # Common NI Variable HTTP endpoints
        endpoints = [
            f"http://{target_host}/ni-vars",
            f"http://{target_host}/nivariable",
            f"http://{target_host}:80/",
        ]
        
        for endpoint in endpoints:
            try:
                print(f"Trying {endpoint}...")
                response = urllib.request.urlopen(endpoint, timeout=3)
                content = response.read().decode('utf-8', errors='ignore')
                print(f"✓ Success! Content:\n{content[:500]}\n")
                return content
            except Exception as e:
                print(f"  Failed: {e}")
    except ImportError:
        print("urllib not available")
    
    return None


if __name__ == "__main__":
    TARGET = "10.20.30.10"
    
    print("=" * 60)
    print("NI LabVIEW Shared Variable Discovery")
    print("=" * 60)
    
    # Method 1: mDNS discovery
    discovered = discover_ni_variables(TARGET, timeout=5)
    
    if not discovered:
        print("\nNo mDNS responses received. Trying direct methods...\n")
    
    # Method 2: Direct port scan
    ports = discover_ni_direct(TARGET)
    
    # Method 3: HTTP API
    http_vars = try_http_variable_list(TARGET)
    
    print("\n" + "=" * 60)
    print("Discovery complete!")
    print("=" * 60)
    
    if discovered or ports:
        print("\nNext steps:")
        print("1. Check if NI Variable Engine is accessible on port 2343 or 3580")
        print("2. Install pythonnet: pip install pythonnet")
        print("3. Use NetworkVariable API to read/write variables")
    else:
        print("\nNo NI services found. Please verify:")
        print("- LabVIEW server is running on 10.20.30.10")
        print("- Firewall allows connections")
        print("- Shared Variable Engine is enabled")
