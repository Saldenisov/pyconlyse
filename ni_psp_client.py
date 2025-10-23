"""
NI PSP Variable Client - Works with ni.var.psp:// URLs

Example URL: ni.var.psp://eureka/SUPERVISION/C1011NI6602

This uses the NI Variable protocol over PSP (port 3580)
Requires pythonnet and NI assemblies, or uses HTTP/DataSocket fallback
"""

import socket
import struct
import urllib.request
import urllib.error
from urllib.parse import urlparse


class NIPSPClient:
    """Client for NI PSP variables"""
    
    def __init__(self):
        self.variables_cache = []
        
    def parse_psp_url(self, psp_url):
        """
        Parse ni.var.psp://hostname/library/variable URL
        
        Returns: (hostname, library, variable)
        """
        if not psp_url.startswith("ni.var.psp://"):
            raise ValueError("URL must start with ni.var.psp://")
        
        # Remove protocol
        path = psp_url.replace("ni.var.psp://", "")
        parts = path.split("/")
        
        if len(parts) < 3:
            raise ValueError("URL format: ni.var.psp://hostname/library/variable")
        
        hostname = parts[0]
        library = parts[1]
        variable = "/".join(parts[2:])  # Variable name might contain /
        
        return hostname, library, variable
    
    def discover_variables_from_pattern(self, hostname, library):
        """
        Try to discover variables in a library using various methods
        """
        print(f"Discovering variables in {library} on {hostname}...")
        
        discovered = []
        
        # Method 1: Try HTTP DataSocket endpoint
        http_urls = [
            f"http://{hostname}/ni-variable/{library}",
            f"http://{hostname}/{library}",
            f"http://{hostname}:3580/{library}",
        ]
        
        for url in http_urls:
            try:
                print(f"  Trying {url}...")
                response = urllib.request.urlopen(url, timeout=3)
                content = response.read().decode('utf-8', errors='ignore')
                print(f"    ✓ Response received ({len(content)} bytes)")
                
                # Parse content for variable names
                # This is heuristic - may need adjustment
                if content:
                    print(f"    Content preview: {content[:200]}")
                    discovered.append(content)
                    
            except urllib.error.HTTPError as e:
                print(f"    ✗ HTTP {e.code}")
            except urllib.error.URLError as e:
                print(f"    ✗ {e.reason}")
            except Exception as e:
                print(f"    ✗ {e}")
        
        # Method 2: Try to connect to PSP port and enumerate
        try:
            print(f"  Trying PSP protocol on port 3580...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((hostname, 3580))
            
            # Try to send enumerate command for this library
            enum_request = self._build_enum_request(library)
            sock.send(enum_request)
            
            response = sock.recv(4096)
            if response:
                print(f"    ✓ Response: {len(response)} bytes")
                print(f"    Hex: {response[:100].hex()}")
                discovered.append(response)
            
            sock.close()
            
        except Exception as e:
            print(f"    ✗ PSP connection failed: {e}")
        
        return discovered
    
    def _build_enum_request(self, library):
        """Build PSP enumerate request for a library"""
        # This is speculative - PSP protocol is proprietary
        lib_bytes = library.encode('utf-8')
        
        # Try different request formats
        requests = [
            b'\x02\x00\x00\x00' + struct.pack('<I', len(lib_bytes)) + lib_bytes,
            b'ENUM\x00' + lib_bytes + b'\x00',
            struct.pack('<I', len(lib_bytes)) + lib_bytes + b'\x00',
        ]
        
        return requests[0]  # Return first one to try
    
    def test_variable_access(self, psp_url):
        """
        Test if a variable is accessible
        
        Args:
            psp_url: Full PSP URL like ni.var.psp://eureka/SUPERVISION/C1011NI6602
        """
        hostname, library, variable = self.parse_psp_url(psp_url)
        
        print("="*60)
        print(f"Testing Variable Access")
        print("="*60)
        print(f"  URL: {psp_url}")
        print(f"  Host: {hostname}")
        print(f"  Library: {library}")
        print(f"  Variable: {variable}")
        print("="*60)
        
        # Method 1: Try as DataSocket URL
        print("\n[Method 1] DataSocket HTTP Access")
        self._try_datasocket_http(hostname, library, variable)
        
        # Method 2: Try PSP direct
        print("\n[Method 2] PSP Protocol (port 3580)")
        self._try_psp_read(hostname, library, variable)
        
        # Method 3: Try as UNC path (for .NET APIs)
        print("\n[Method 3] UNC Path Format")
        unc_path = f"\\\\{hostname}\\{library}\\{variable}"
        print(f"  UNC: {unc_path}")
        print(f"  Use with NI .NET APIs after installing NI software")
    
    def _try_datasocket_http(self, hostname, library, variable):
        """Try to access via HTTP DataSocket"""
        urls = [
            f"http://{hostname}/ni-variable/{library}/{variable}",
            f"http://{hostname}/{library}/{variable}",
            f"http://{hostname}:3580/{library}/{variable}",
        ]
        
        for url in urls:
            try:
                print(f"  GET {url}")
                req = urllib.request.Request(url)
                req.add_header('Accept', '*/*')
                response = urllib.request.urlopen(req, timeout=3)
                
                content = response.read()
                print(f"    ✓ Success! ({len(content)} bytes)")
                print(f"    Content-Type: {response.headers.get('Content-Type')}")
                
                # Try to parse value
                try:
                    text = content.decode('utf-8')
                    print(f"    Value: {text}")
                except:
                    print(f"    Binary: {content[:50].hex()}")
                
                return content
                
            except urllib.error.HTTPError as e:
                print(f"    ✗ HTTP {e.code}: {e.reason}")
            except urllib.error.URLError as e:
                print(f"    ✗ {e.reason}")
            except Exception as e:
                print(f"    ✗ {e}")
        
        return None
    
    def _try_psp_read(self, hostname, library, variable):
        """Try to read variable via PSP protocol"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((hostname, 3580))
            print(f"  ✓ Connected to {hostname}:3580")
            
            # Build variable path
            var_path = f"{library}/{variable}"
            path_bytes = var_path.encode('utf-8')
            
            # Try different read request formats
            read_requests = [
                # Format 1: Length-prefixed path
                struct.pack('<I', len(path_bytes)) + path_bytes,
                # Format 2: UNC-style path
                f"\\\\{hostname}\\{var_path}".encode('utf-16le'),
                # Format 3: Simple path with null terminator
                path_bytes + b'\x00',
            ]
            
            for i, request in enumerate(read_requests, 1):
                print(f"    Attempt {i}: {request[:50].hex()}...")
                sock.send(request)
                sock.settimeout(2)
                
                try:
                    response = sock.recv(4096)
                    if response and len(response) > 0:
                        print(f"      ✓ Response: {len(response)} bytes")
                        print(f"      Hex: {response[:100].hex()}")
                        
                        # Try to parse as different types
                        self._try_parse_value(response)
                        break
                except socket.timeout:
                    print(f"      ✗ Timeout")
            
            sock.close()
            
        except Exception as e:
            print(f"  ✗ PSP read failed: {e}")
    
    def _try_parse_value(self, data):
        """Try to parse response data as various types"""
        print(f"      Parsing value:")
        
        # Try as float
        if len(data) >= 4:
            try:
                val = struct.unpack('<f', data[:4])[0]
                print(f"        As float: {val}")
            except:
                pass
            
            try:
                val = struct.unpack('<d', data[:8])[0]
                print(f"        As double: {val}")
            except:
                pass
        
        # Try as int
        if len(data) >= 4:
            try:
                val = struct.unpack('<i', data[:4])[0]
                print(f"        As int32: {val}")
            except:
                pass
        
        # Try as string
        try:
            text = data.decode('utf-8', errors='ignore').strip('\x00')
            if text and len(text) < 200:
                print(f"        As string: {text}")
        except:
            pass


def main():
    print("="*70)
    print("NI PSP Variable Client")
    print("="*70)
    
    client = NIPSPClient()
    
    # Test the example variable
    example_url = "ni.var.psp://eureka/SUPERVISION/C1011NI6602"
    
    print(f"\nTesting example variable:")
    print(f"  {example_url}\n")
    
    client.test_variable_access(example_url)
    
    # Try to discover other variables in the library
    print("\n" + "="*70)
    print("Attempting to discover other variables in SUPERVISION library")
    print("="*70)
    
    client.discover_variables_from_pattern("eureka", "SUPERVISION")
    
    print("\n" + "="*70)
    print("Usage Examples")
    print("="*70)
    print("""
# Test a variable
client = NIPSPClient()
client.test_variable_access("ni.var.psp://eureka/SUPERVISION/C1011NI6602")

# Parse URL
hostname, library, variable = client.parse_psp_url("ni.var.psp://eureka/SUPERVISION/C1011NI6602")

# Discover variables
client.discover_variables_from_pattern("eureka", "SUPERVISION")
    """)


if __name__ == "__main__":
    main()
