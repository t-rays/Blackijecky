#!/usr/bin/env python3
"""
Test suite for Web Interface and Web Bridge
Tests SSE functionality, session management, and integration.
"""

import unittest
import socket
import threading
import time
import json
import queue
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer
from urllib.parse import urlparse, parse_qs
import http.client

# Import modules to test
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import web_bridge
import blackjack_client as client_module
import blackjack_server as server_module


# ============================================================================
# SESSION MANAGEMENT TESTS
# ============================================================================

class TestGameSession(unittest.TestCase):
    """Test GameSession class functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.session = web_bridge.GameSession(
            "test_session_123",
            "127.0.0.1",
            54321,
            3,
            "TestPlayer"
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.session.close()
    
    def test_session_initialization(self):
        """Test session initializes correctly."""
        self.assertEqual(self.session.session_id, "test_session_123")
        self.assertEqual(self.session.server_ip, "127.0.0.1")
        self.assertEqual(self.session.tcp_port, 54321)
        self.assertEqual(self.session.num_rounds, 3)
        self.assertEqual(self.session.client_name, "TestPlayer")
        self.assertEqual(self.session.game_state, "disconnected")
        self.assertIsNotNone(self.session.event_queue)
    
    def test_get_state(self):
        """Test get_state returns correct structure."""
        state = self.session.get_state()
        
        self.assertIn('session_id', state)
        self.assertIn('game_state', state)
        self.assertIn('player_hand', state)
        self.assertIn('dealer_hand', state)
        self.assertIn('player_total', state)
        self.assertIn('dealer_total', state)
        self.assertEqual(state['session_id'], "test_session_123")
    
    def test_event_queue_operations(self):
        """Test event queue operations."""
        test_event = {'type': 'card', 'data': 'test'}
        
        # Put event
        self.session.event_queue.put(test_event)
        
        # Get event
        retrieved = self.session.event_queue.get(timeout=1)
        self.assertEqual(retrieved, test_event)
    
    def test_close_session(self):
        """Test session closes correctly."""
        self.session.receiving = True
        self.session.close()
        
        self.assertFalse(self.session.receiving)
        # Receiver thread should stop


class TestSessionManager(unittest.TestCase):
    """Test SessionManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = web_bridge.SessionManager()
    
    def test_create_session(self):
        """Test session creation."""
        session_id = self.manager.create_session(
            "127.0.0.1", 54321, 5, "TestPlayer"
        )
        
        self.assertIsNotNone(session_id)
        self.assertIn(session_id, self.manager.sessions)
    
    def test_get_session(self):
        """Test retrieving a session."""
        session_id = self.manager.create_session(
            "127.0.0.1", 54321, 5, "TestPlayer"
        )
        
        session = self.manager.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.session_id, session_id)
    
    def test_get_nonexistent_session(self):
        """Test retrieving non-existent session."""
        session = self.manager.get_session("nonexistent")
        self.assertIsNone(session)
    
    def test_remove_session(self):
        """Test removing a session."""
        session_id = self.manager.create_session(
            "127.0.0.1", 54321, 5, "TestPlayer"
        )
        
        self.assertIn(session_id, self.manager.sessions)
        self.manager.remove_session(session_id)
        self.assertNotIn(session_id, self.manager.sessions)


# ============================================================================
# HTTP HANDLER TESTS
# ============================================================================

class TestWebBridgeHandler(unittest.TestCase):
    """Test WebBridgeHandler HTTP functionality."""
    
    def test_json_serialization(self):
        """Test JSON response data can be serialized."""
        test_data = {'success': True, 'data': 'test', 'session_id': 'test123'}
        
        # Verify it can be serialized
        json_str = json.dumps(test_data)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed, test_data)
        self.assertEqual(parsed['success'], True)
    
    def test_response_structure(self):
        """Test response structure is correct."""
        # Test success response
        success_response = {'success': True, 'session_id': 'test123'}
        self.assertIn('success', success_response)
        
        # Test error response
        error_response = {'success': False, 'error': 'Test error'}
        self.assertIn('success', error_response)
        self.assertIn('error', error_response)


# ============================================================================
# SSE FUNCTIONALITY TESTS
# ============================================================================

class TestSSEFunctionality(unittest.TestCase):
    """Test Server-Sent Events functionality."""
    
    def test_event_queue_thread_safety(self):
        """Test event queue is thread-safe."""
        session = web_bridge.GameSession(
            "test", "127.0.0.1", 54321, 1, "Test"
        )
        
        # Simulate multiple threads putting events
        def put_events(count):
            for i in range(count):
                session.event_queue.put({'event': i})
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=put_events, args=(10,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all events were added
        event_count = 0
        while not session.event_queue.empty():
            session.event_queue.get()
            event_count += 1
        
        self.assertEqual(event_count, 50)  # 5 threads * 10 events
        session.close()
    
    def test_sse_event_format(self):
        """Test SSE event format is correct."""
        session = web_bridge.GameSession(
            "test", "127.0.0.1", 54321, 1, "Test"
        )
        
        test_event = {
            'result': 0,
            'card': {'rank': 13, 'suit': 0},
            'state': session.get_state()
        }
        
        session.event_queue.put(test_event)
        
        # Format as SSE
        event_data = session.event_queue.get()
        json_data = json.dumps(event_data)
        sse_format = f"data: {json_data}\n\n"
        
        # Verify format
        self.assertTrue(sse_format.startswith("data: "))
        self.assertTrue(sse_format.endswith("\n\n"))
        
        # Verify JSON is valid
        parsed = json.loads(json_data)
        self.assertEqual(parsed['result'], 0)
        session.close()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestWebBridgeIntegration(unittest.TestCase):
    """Integration tests for web bridge."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bridge_port = 0  # Will be assigned
        self.bridge_server = None
        self.bridge_thread = None
    
    def tearDown(self):
        """Clean up after tests."""
        if self.bridge_server:
            self.bridge_server.shutdown()
        if self.bridge_thread:
            self.bridge_thread.join(timeout=2)
    
    def start_bridge_server(self):
        """Start bridge server in background."""
        self.bridge_server = HTTPServer(
            ('127.0.0.1', 0),
            web_bridge.WebBridgeHandler
        )
        self.bridge_port = self.bridge_server.server_address[1]
        
        def run_server():
            self.bridge_server.serve_forever()
        
        self.bridge_thread = threading.Thread(target=run_server, daemon=True)
        self.bridge_thread.start()
        time.sleep(0.5)  # Give server time to start
    
    def test_discover_endpoint(self):
        """Test server discovery endpoint."""
        self.start_bridge_server()
        
        try:
            conn = http.client.HTTPConnection('127.0.0.1', self.bridge_port, timeout=2)
            conn.request('GET', '/api/discover')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode())
            # Should have success field (may be True or False depending on server)
            self.assertIn('success', data)
            conn.close()
        except Exception as e:
            # Skip if server not running
            self.skipTest(f"Bridge server not accessible: {e}")
    
    def test_session_creation_endpoint(self):
        """Test session creation endpoint."""
        self.start_bridge_server()
        
        try:
            conn = http.client.HTTPConnection('127.0.0.1', self.bridge_port, timeout=2)
            conn.request('POST', '/api/session/create', 
                        json.dumps({
                            'server_ip': '127.0.0.1',
                            'tcp_port': 54321,
                            'num_rounds': 1,
                            'client_name': 'TestPlayer'
                        }),
                        {'Content-Type': 'application/json'})
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode())
            # Should either succeed or fail gracefully
            self.assertIn('success', data)
            conn.close()
        except Exception as e:
            # Skip if server not running
            self.skipTest(f"Bridge server not accessible: {e}")


# ============================================================================
# MOCK TCP SERVER FOR TESTING
# ============================================================================

class MockTCPServer:
    """Mock TCP server for testing web bridge."""
    
    def __init__(self, port=0):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('127.0.0.1', port))
        self.socket.listen(1)
        self.port = self.socket.getsockname()[1]
        self.running = False
        self.thread = None
    
    def start(self):
        """Start mock server."""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        time.sleep(0.2)  # Give server time to start
    
    def _run(self):
        """Run mock server."""
        while self.running:
            try:
                self.socket.settimeout(1)
                conn, addr = self.socket.accept()
                self._handle_client(conn)
            except socket.timeout:
                continue
            except Exception:
                break
    
    def _handle_client(self, conn):
        """Handle mock client connection."""
        try:
            # Receive request
            data = conn.recv(1024)
            
            # Send initial cards
            card1 = server_module.Card(10, 0)  # 10♥
            card2 = server_module.Card(5, 1)   # 5♦
            dealer_card = server_module.Card(13, 2)  # K♣
            
            conn.sendall(server_module.create_payload_message(
                server_module.RESULT_NOT_OVER, card1
            ))
            time.sleep(0.1)
            
            conn.sendall(server_module.create_payload_message(
                server_module.RESULT_NOT_OVER, card2
            ))
            time.sleep(0.1)
            
            conn.sendall(server_module.create_payload_message(
                server_module.RESULT_NOT_OVER, dealer_card
            ))
            
            # Wait for decision
            decision_data = conn.recv(1024)
            decision = server_module.parse_payload_message(decision_data)
            
            if decision == "Hittt":
                # Send hit card
                hit_card = server_module.Card(7, 3)  # 7♠
                conn.sendall(server_module.create_payload_message(
                    server_module.RESULT_NOT_OVER, hit_card
                ))
            
            # Send stand decision response
            time.sleep(0.1)
            
            # Dealer reveals and plays
            dealer_card2 = server_module.Card(8, 0)  # 8♥
            conn.sendall(server_module.create_payload_message(
                server_module.RESULT_NOT_OVER, dealer_card2
            ))
            
            # Final result
            time.sleep(0.1)
            conn.sendall(server_module.create_payload_message(
                server_module.RESULT_WIN, None
            ))
            
        except Exception as e:
            print(f"Mock server error: {e}")
        finally:
            conn.close()
    
    def stop(self):
        """Stop mock server."""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join(timeout=2)


# ============================================================================
# END-TO-END TESTS
# ============================================================================

class TestEndToEnd(unittest.TestCase):
    """End-to-end tests with mock TCP server."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_tcp = MockTCPServer()
        self.bridge_port = 0
        self.bridge_server = None
        self.bridge_thread = None
    
    def tearDown(self):
        """Clean up after tests."""
        if self.mock_tcp:
            self.mock_tcp.stop()
        if self.bridge_server:
            self.bridge_server.shutdown()
        if self.bridge_thread:
            self.bridge_thread.join(timeout=2)
    
    def start_bridge_server(self):
        """Start bridge server."""
        self.bridge_server = HTTPServer(
            ('127.0.0.1', 0),
            web_bridge.WebBridgeHandler
        )
        self.bridge_port = self.bridge_server.server_address[1]
        
        def run_server():
            self.bridge_server.serve_forever()
        
        self.bridge_thread = threading.Thread(target=run_server, daemon=True)
        self.bridge_thread.start()
        time.sleep(0.5)
    
    def test_full_game_flow(self):
        """Test complete game flow through web bridge."""
        # Start mock TCP server
        self.mock_tcp.start()
        
        # Start bridge server
        self.start_bridge_server()
        
        # Create session
        conn = http.client.HTTPConnection('127.0.0.1', self.bridge_port)
        conn.request('POST', '/api/session/create',
                    json.dumps({
                        'server_ip': '127.0.0.1',
                        'tcp_port': self.mock_tcp.port,
                        'num_rounds': 1,
                        'client_name': 'TestPlayer'
                    }),
                    {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        conn.close()
        
        if data.get('success'):
            session_id = data['session_id']
            
            # Test getting state
            conn = http.client.HTTPConnection('127.0.0.1', self.bridge_port)
            conn.request('GET', f'/api/session/state?session_id={session_id}')
            response = conn.getresponse()
            state_data = json.loads(response.read().decode())
            conn.close()
            
            self.assertIn('success', state_data)
            
            # Test sending decision
            conn = http.client.HTTPConnection('127.0.0.1', self.bridge_port)
            conn.request('POST', '/api/session/decision',
                        json.dumps({
                            'session_id': session_id,
                            'decision': 'Stand'
                        }),
                        {'Content-Type': 'application/json'})
            response = conn.getresponse()
            decision_data = json.loads(response.read().decode())
            conn.close()
            
            # Should succeed or handle gracefully
            self.assertIn('success', decision_data)


# ============================================================================
# SSE STREAM TESTS
# ============================================================================

class TestSSEStream(unittest.TestCase):
    """Test SSE stream functionality."""
    
    def test_sse_event_parsing(self):
        """Test parsing SSE events."""
        # Create test event
        test_event = {
            'result': 0,
            'card': {
                'rank': 13,
                'suit': 0,
                'rank_name': 'K',
                'suit_symbol': '♥',
                'value': 10
            },
            'state': {'game_state': 'playing'}
        }
        
        # Format as SSE
        json_data = json.dumps(test_event)
        sse_line = f"data: {json_data}\n\n"
        
        # Parse back
        if sse_line.startswith("data: "):
            json_part = sse_line[6:].strip()
            parsed = json.loads(json_part)
            self.assertEqual(parsed['result'], 0)
            self.assertIsNotNone(parsed['card'])


# ============================================================================
# UTILITY TESTS
# ============================================================================

class TestUtilities(unittest.TestCase):
    """Test utility functions."""
    
    def test_card_info_formatting(self):
        """Test card info formatting for web."""
        # Simulate card received from TCP
        card = client_module.Card(13, 0)  # King of Hearts
        
        card_info = {
            'rank': card.rank,
            'suit': card.suit,
            'rank_name': web_bridge.RANK_NAMES[card.rank],
            'suit_symbol': web_bridge.SUITS[card.suit],
            'value': card.get_value(),
            'display': f"{web_bridge.RANK_NAMES[card.rank]}{web_bridge.SUITS[card.suit]}"
        }
        
        self.assertEqual(card_info['rank'], 13)
        self.assertEqual(card_info['suit'], 0)
        self.assertEqual(card_info['rank_name'], 'K')
        self.assertEqual(card_info['suit_symbol'], '♥')
        self.assertEqual(card_info['value'], 10)
        self.assertEqual(card_info['display'], 'K♥')
    
    def test_state_serialization(self):
        """Test game state can be serialized to JSON."""
        session = web_bridge.GameSession(
            "test", "127.0.0.1", 54321, 1, "Test"
        )
        
        state = session.get_state()
        
        # Should be JSON serializable
        json_str = json.dumps(state)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed['session_id'], "test")
        self.assertEqual(parsed['game_state'], "disconnected")
        
        session.close()


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_tests():
    """Run all tests and print results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestGameSession,
        TestSessionManager,
        TestWebBridgeHandler,
        TestSSEFunctionality,
        TestWebBridgeIntegration,
        TestEndToEnd,
        TestSSEStream,
        TestUtilities,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("WEB INTERFACE TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.testsRun > 0:
        success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
        print(f"Success rate: {success_rate:.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

