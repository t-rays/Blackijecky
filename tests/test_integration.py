#!/usr/bin/env python3
"""
Integration test script for Blackjack Client-Server
This script runs a real server and client to test end-to-end functionality.
"""

import subprocess
import time
import socket
import sys
import signal
import os


def find_free_port():
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def test_server_startup():
    """Test that server starts correctly."""
    print("Testing server startup...")
    try:
        # Start server in background
        server_process = subprocess.Popen(
            [sys.executable, 'blackjack_server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give server time to start
        time.sleep(2)
        
        # Check if server is still running
        if server_process.poll() is None:
            print("✓ Server started successfully")
            server_process.terminate()
            server_process.wait(timeout=5)
            return True
        else:
            stdout, stderr = server_process.communicate()
            print(f"✗ Server failed to start")
            print(f"  stdout: {stdout}")
            print(f"  stderr: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing server startup: {e}")
        return False


def test_udp_broadcast():
    """Test UDP broadcast functionality."""
    print("\nTesting UDP broadcast...")
    try:
        # Start server
        server_process = subprocess.Popen(
            [sys.executable, 'blackjack_server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        time.sleep(2)  # Wait for server to start
        
        # Create UDP socket to receive broadcast
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(('', 13122))
        udp_socket.settimeout(3)
        
        # Try to receive broadcast
        try:
            data, addr = udp_socket.recvfrom(1024)
            print(f"✓ Received UDP broadcast from {addr}")
            
            # Parse the message
            import blackjack_client as client_module
            result = client_module.parse_offer_message(data)
            if result:
                tcp_port, server_name = result
                print(f"✓ Parsed offer: {server_name} on port {tcp_port}")
                udp_socket.close()
                server_process.terminate()
                server_process.wait(timeout=5)
                return True
            else:
                print("✗ Failed to parse offer message")
                udp_socket.close()
                server_process.terminate()
                server_process.wait(timeout=5)
                return False
        except socket.timeout:
            print("✗ Did not receive UDP broadcast within timeout")
            udp_socket.close()
            server_process.terminate()
            server_process.wait(timeout=5)
            return False
            
    except Exception as e:
        print(f"✗ Error testing UDP broadcast: {e}")
        if 'server_process' in locals():
            server_process.terminate()
        return False


def test_message_encoding():
    """Test message encoding/decoding."""
    print("\nTesting message encoding/decoding...")
    try:
        import blackjack_server as server_module
        import blackjack_client as client_module
        
        # Test offer message
        offer = server_module.create_offer_message(54321, "TestServer")
        tcp_port, name = client_module.parse_offer_message(offer)
        assert tcp_port == 54321, f"Expected port 54321, got {tcp_port}"
        assert name == "TestServer", f"Expected 'TestServer', got '{name}'"
        print("✓ Offer message encoding/decoding works")
        
        # Test request message
        request = client_module.create_request_message(5, "TestClient")
        num_rounds, client_name = server_module.parse_request_message(request)
        assert num_rounds == 5, f"Expected 5 rounds, got {num_rounds}"
        assert client_name == "TestClient", f"Expected 'TestClient', got '{client_name}'"
        print("✓ Request message encoding/decoding works")
        
        # Test payload messages
        card = server_module.Card(13, 0)
        payload = server_module.create_payload_message(
            server_module.RESULT_WIN, card
        )
        result, parsed_card = client_module.parse_payload_message(payload)
        assert result == server_module.RESULT_WIN
        assert parsed_card is not None
        assert parsed_card.rank == 13
        print("✓ Payload message encoding/decoding works")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing message encoding: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_card_logic():
    """Test card and game logic."""
    print("\nTesting card and game logic...")
    try:
        import blackjack_server as server_module
        
        # Test card values
        ace = server_module.Card(1, 0)
        assert ace.get_value() == 11, "Ace should be worth 11"
        
        jack = server_module.Card(11, 0)
        assert jack.get_value() == 10, "Jack should be worth 10"
        
        five = server_module.Card(5, 0)
        assert five.get_value() == 5, "Five should be worth 5"
        print("✓ Card values are correct")
        
        # Test game logic
        game = server_module.BlackjackGame()
        game.player_total = 22
        game.dealer_total = 15
        result = game.determine_winner()
        assert result == server_module.RESULT_LOSS, "Player bust should lose"
        
        game.player_total = 18
        game.dealer_total = 22
        result = game.determine_winner()
        assert result == server_module.RESULT_WIN, "Dealer bust should mean player wins"
        
        game.player_total = 20
        game.dealer_total = 18
        result = game.determine_winner()
        assert result == server_module.RESULT_WIN, "Higher total should win"
        
        game.player_total = 18
        game.dealer_total = 18
        result = game.determine_winner()
        assert result == server_module.RESULT_TIE, "Equal totals should tie"
        print("✓ Game logic is correct")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing card logic: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("="*60)
    print("BLACKJACK INTEGRATION TESTS")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Message Encoding", test_message_encoding()))
    results.append(("Card Logic", test_card_logic()))
    results.append(("Server Startup", test_server_startup()))
    results.append(("UDP Broadcast", test_udp_broadcast()))
    
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
    print(f"Success rate: {passed/len(results)*100:.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

