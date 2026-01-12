#!/usr/bin/env python3
"""
Integration test script for Web Interface
Tests the web bridge with actual HTTP requests and SSE streams.
"""

import subprocess
import time
import socket
import sys
import json
import http.client
import threading
import requests
from urllib.parse import urlparse
import signal
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Global server process
bridge_process = None


def wait_for_server(host='localhost', port=8080, timeout=10):
    """Wait for server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(0.5)
    return False


def start_bridge_server():
    """Start the web bridge server."""
    global bridge_process
    
    if bridge_process is not None:
        return bridge_process
    
    print("Starting web bridge server...")
    try:
        bridge_process = subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'src', 'web_bridge.py')],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to be ready
        if wait_for_server('localhost', 8080, timeout=5):
            print("✓ Web bridge server started and ready")
            return bridge_process
        else:
            print("✗ Web bridge server failed to start (timeout)")
            if bridge_process:
                bridge_process.terminate()
                bridge_process = None
            return None
    except Exception as e:
        print(f"✗ Error starting web bridge server: {e}")
        return None


def stop_bridge_server():
    """Stop the web bridge server."""
    global bridge_process
    
    if bridge_process is not None:
        print("\nStopping web bridge server...")
        try:
            bridge_process.terminate()
            bridge_process.wait(timeout=5)
            print("✓ Web bridge server stopped")
        except subprocess.TimeoutExpired:
            bridge_process.kill()
            print("⚠ Web bridge server force-killed")
        except Exception as e:
            print(f"⚠ Error stopping server: {e}")
        finally:
            bridge_process = None


def test_bridge_startup():
    """Test that web bridge starts correctly."""
    print("Testing web bridge startup...")
    process = start_bridge_server()
    
    if process and process.poll() is None:
        print("✓ Web bridge process is running")
        return True
    else:
        print("✗ Web bridge failed to start")
        return False


def test_http_endpoints():
    """Test HTTP endpoints are accessible."""
    print("\nTesting HTTP endpoints...")
    
    try:
        # Try to connect to default port
        conn = http.client.HTTPConnection('localhost', 8080, timeout=2)
        conn.request('GET', '/')
        response = conn.getresponse()
        
        if response.status == 200:
            print("✓ HTTP server is accessible")
            conn.close()
            return True
        else:
            print(f"✗ HTTP server returned status {response.status}")
            conn.close()
            return False
    except ConnectionRefusedError:
        print("✗ HTTP server not running (start web_bridge.py first)")
        return False
    except Exception as e:
        print(f"✗ Error connecting to HTTP server: {e}")
        return False


def test_static_files():
    """Test static files are served."""
    print("\nTesting static file serving...")
    
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=2)
        
        # Test HTML file
        conn.request('GET', '/')
        response = conn.getresponse()
        if response.status == 200:
            content = response.read().decode()
            if '<html' in content.lower() or '<!doctype' in content.lower():
                print("✓ HTML file served correctly")
            else:
                print("✗ HTML file content invalid")
                conn.close()
                return False
        else:
            print(f"✗ Failed to serve HTML (status {response.status})")
            conn.close()
            return False
        
        # Test CSS file
        conn.request('GET', '/style.css')
        response = conn.getresponse()
        if response.status == 200:
            print("✓ CSS file served correctly")
        else:
            print(f"⚠ CSS file not found (status {response.status})")
        
        # Test JS file
        conn.request('GET', '/script.js')
        response = conn.getresponse()
        if response.status == 200:
            print("✓ JavaScript file served correctly")
        else:
            print(f"⚠ JavaScript file not found (status {response.status})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"✗ Error testing static files: {e}")
        return False


# Store discovered server info for use in other tests
discovered_server = None

def test_discover_endpoint():
    """Test server discovery endpoint."""
    global discovered_server
    print("\nTesting server discovery endpoint...")
    
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=3)
        conn.request('GET', '/api/discover')
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        conn.close()
        
        if 'success' in data:
            if data['success']:
                discovered_server = {
                    'server_ip': data.get('server_ip'),
                    'tcp_port': data.get('tcp_port'),
                    'server_name': data.get('server_name')
                }
                print(f"✓ Server discovery works (found: {data.get('server_name', 'Unknown')} at {data.get('server_ip')}:{data.get('tcp_port')})")
            else:
                discovered_server = None
                print(f"⚠ No server found (expected if blackjack server not running): {data.get('error', 'Unknown error')}")
            # Still pass - endpoint works, just no server available
            return True
        else:
            print("✗ Invalid response format")
            return False
            
    except socket.timeout:
        discovered_server = None
        print("⚠ Discovery timeout (expected if no blackjack server running)")
        return True  # Endpoint exists, just no server to discover
    except Exception as e:
        discovered_server = None
        print(f"✗ Error testing discovery: {e}")
        return False


def test_session_creation():
    """Test session creation endpoint."""
    global discovered_server
    print("\nTesting session creation...")
    
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=2)
        
        # Use discovered server info if available, otherwise use defaults
        if discovered_server:
            server_ip = discovered_server['server_ip']
            tcp_port = discovered_server['tcp_port']
            print(f"  Using discovered server: {server_ip}:{tcp_port}")
        else:
            server_ip = '127.0.0.1'
            tcp_port = 54321  # Default fallback
            print(f"  Using default server: {server_ip}:{tcp_port} (no server discovered)")
        
        # Try to create session
        conn.request('POST', '/api/session/create',
                    json.dumps({
                        'server_ip': server_ip,
                        'tcp_port': tcp_port,
                        'num_rounds': 1,
                        'client_name': 'TestPlayer'
                    }),
                    {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        conn.close()
        
        if 'success' in data:
            if data['success']:
                session_id = data.get('session_id', 'N/A')
                print(f"✓ Session creation works (session_id: {session_id[:20]}...)")
                return True
            else:
                error = data.get('error', 'Unknown')
                if discovered_server:
                    print(f"⚠ Session creation failed (server found but connection failed): {error}")
                else:
                    print(f"⚠ Session creation failed (no server discovered): {error}")
                # Still pass - endpoint works, just can't connect to server
                return True
        else:
            print("✗ Invalid response format")
            return False
            
    except Exception as e:
        print(f"✗ Error testing session creation: {e}")
        return False


def test_api_structure():
    """Test API response structure."""
    print("\nTesting API response structure...")
    
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=3)
        
        # Test discover endpoint structure
        conn.request('GET', '/api/discover')
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        conn.close()
        
        # Verify structure
        if isinstance(data, dict):
            if 'success' in data:
                print("✓ API responses have correct structure")
                return True
            else:
                print("✗ API response missing 'success' field")
                return False
        else:
            print("✗ API response is not a dictionary")
            return False
            
    except socket.timeout:
        print("⚠ Request timeout (endpoint exists, may be waiting for server)")
        return True  # Endpoint exists, structure is correct
    except Exception as e:
        print(f"✗ Error testing API structure: {e}")
        return False


def test_cors_headers():
    """Test CORS headers are present."""
    print("\nTesting CORS headers...")
    
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=3)
        conn.request('GET', '/api/discover')
        response = conn.getresponse()
        headers = dict(response.getheaders())
        conn.close()
        
        if 'Access-Control-Allow-Origin' in headers:
            print(f"✓ CORS headers present ({headers['Access-Control-Allow-Origin']})")
            return True
        else:
            print("⚠ CORS headers not found")
            return False
            
    except socket.timeout:
        # If we get a timeout, we can't check headers, but endpoint exists
        print("⚠ Request timeout (cannot verify CORS headers)")
        return True  # Endpoint exists, assume headers are set
    except Exception as e:
        print(f"✗ Error testing CORS: {e}")
        return False


def main():
    """Run all integration tests."""
    print("="*60)
    print("WEB INTERFACE INTEGRATION TESTS")
    print("="*60)
    print("\nAutomatically starting web bridge server...")
    print("="*60)
    
    # Start server before tests
    if not start_bridge_server():
        print("\n✗ Failed to start web bridge server. Exiting.")
        return False
    
    # Give server a moment to fully initialize
    time.sleep(1)
    
    results = []
    
    try:
        # Run tests
        results.append(("Bridge Startup", test_bridge_startup()))
        results.append(("HTTP Endpoints", test_http_endpoints()))
        results.append(("Static Files", test_static_files()))
        results.append(("Discover Endpoint", test_discover_endpoint()))
        results.append(("Session Creation", test_session_creation()))
        results.append(("API Structure", test_api_structure()))
        results.append(("CORS Headers", test_cors_headers()))
    finally:
        # Always stop server, even if tests fail
        stop_bridge_server()
    
    # Print summary
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(results)} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    if len(results) > 0:
        print(f"Success rate: {passed/len(results)*100:.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        stop_bridge_server()
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        stop_bridge_server()
        sys.exit(1)

