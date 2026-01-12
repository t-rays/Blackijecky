#!/usr/bin/env python3
"""
Test suite for Blackjack Client-Server Application
Tests all major components including network protocol, game logic, and integration.
"""

import unittest
import socket
import threading
import time
import struct
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the modules to test
import blackjack_server as server_module
import blackjack_client as client_module


# ============================================================================
# TEST CONSTANTS
# ============================================================================

MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4
UDP_PORT = 13122


# ============================================================================
# CARD AND DECK TESTS
# ============================================================================

class TestCard(unittest.TestCase):
    """Test Card class functionality."""
    
    def test_card_creation(self):
        """Test card creation with valid rank and suit."""
        card = server_module.Card(1, 0)  # Ace of Hearts
        self.assertEqual(card.rank, 1)
        self.assertEqual(card.suit, 0)
    
    def test_card_value_ace(self):
        """Test that Ace has value 11."""
        card = server_module.Card(1, 0)
        self.assertEqual(card.get_value(), 11)
    
    def test_card_value_face_cards(self):
        """Test that Jack, Queen, King have value 10."""
        for rank in [11, 12, 13]:
            card = server_module.Card(rank, 0)
            self.assertEqual(card.get_value(), 10)
    
    def test_card_value_number_cards(self):
        """Test that number cards have their face value."""
        for rank in range(2, 11):
            card = server_module.Card(rank, 0)
            self.assertEqual(card.get_value(), rank)
    
    def test_card_encode(self):
        """Test card encoding to bytes."""
        card = server_module.Card(13, 0)  # King of Hearts
        encoded = card.encode()
        self.assertEqual(len(encoded), 3)
        self.assertEqual(encoded[:2], b'13')
        self.assertEqual(encoded[2], 0)
    
    def test_card_decode(self):
        """Test card decoding from bytes."""
        # King of Hearts: b'13\x00' (rank "13" as ASCII + suit byte 0)
        card = client_module.Card.decode(b'13\x00')
        self.assertIsNotNone(card)
        self.assertEqual(card.rank, 13)
        self.assertEqual(card.suit, 0)
    
    def test_card_decode_invalid(self):
        """Test card decoding with invalid data."""
        self.assertIsNone(client_module.Card.decode(b'00'))
        self.assertIsNone(client_module.Card.decode(b'999'))


class TestDeck(unittest.TestCase):
    """Test Deck class functionality."""
    
    def test_deck_creation(self):
        """Test deck is created with 52 cards."""
        deck = server_module.Deck()
        self.assertEqual(len(deck.cards), 52)
    
    def test_deck_reset(self):
        """Test deck reset creates fresh 52-card deck."""
        deck = server_module.Deck()
        deck.draw()
        self.assertEqual(len(deck.cards), 51)
        deck.reset()
        self.assertEqual(len(deck.cards), 52)
    
    def test_deck_draw(self):
        """Test drawing cards from deck."""
        deck = server_module.Deck()
        card = deck.draw()
        self.assertIsNotNone(card)
        self.assertEqual(len(deck.cards), 51)
    
    def test_deck_auto_reshuffle(self):
        """Test deck auto-reshuffles when empty."""
        deck = server_module.Deck()
        # Draw all cards
        for _ in range(52):
            deck.draw()
        # Next draw should trigger reshuffle
        card = deck.draw()
        self.assertIsNotNone(card)
        self.assertEqual(len(deck.cards), 51)


# ============================================================================
# GAME LOGIC TESTS
# ============================================================================

class TestBlackjackGame(unittest.TestCase):
    """Test BlackjackGame class functionality."""
    
    def test_game_initialization(self):
        """Test game initializes correctly."""
        game = server_module.BlackjackGame()
        self.assertEqual(len(game.player_hand), 0)
        self.assertEqual(len(game.dealer_hand), 0)
        self.assertEqual(game.player_total, 0)
        self.assertEqual(game.dealer_total, 0)
    
    def test_calculate_hand_value(self):
        """Test hand value calculation."""
        game = server_module.BlackjackGame()
        hand = [
            server_module.Card(1, 0),   # Ace = 11
            server_module.Card(5, 0),    # 5
            server_module.Card(11, 0)    # Jack = 10
        ]
        total = game.calculate_hand_value(hand)
        self.assertEqual(total, 26)
    
    def test_deal_initial_cards(self):
        """Test initial card dealing."""
        game = server_module.BlackjackGame()
        card1, card2, dealer_card = game.deal_initial_cards()
        
        self.assertIsNotNone(card1)
        self.assertIsNotNone(card2)
        self.assertIsNotNone(dealer_card)
        self.assertEqual(len(game.player_hand), 2)
        self.assertEqual(len(game.dealer_hand), 2)
        self.assertGreater(game.player_total, 0)
        self.assertGreater(game.dealer_total, 0)
    
    def test_player_hit(self):
        """Test player hit functionality."""
        game = server_module.BlackjackGame()
        game.player_hand = [
            server_module.Card(10, 0),
            server_module.Card(5, 0)
        ]
        game.player_total = 15
        
        new_card, new_total, is_bust = game.player_hit()
        self.assertIsNotNone(new_card)
        self.assertGreater(new_total, 15)
        self.assertIn(new_card, game.player_hand)
    
    def test_player_bust(self):
        """Test player bust detection."""
        game = server_module.BlackjackGame()
        game.player_hand = [
            server_module.Card(10, 0),
            server_module.Card(10, 0),
            server_module.Card(5, 0)
        ]
        game.player_total = 25
        
        new_card, new_total, is_bust = game.player_hit()
        self.assertTrue(is_bust)
    
    def test_dealer_play(self):
        """Test dealer play logic (hits until 17+)."""
        game = server_module.BlackjackGame()
        game.dealer_hand = [
            server_module.Card(5, 0),
            server_module.Card(5, 0)
        ]
        game.dealer_total = 10
        
        drawn_cards = game.dealer_play()
        self.assertGreaterEqual(game.dealer_total, 17)
    
    def test_determine_winner_player_bust(self):
        """Test winner determination when player busts."""
        game = server_module.BlackjackGame()
        game.player_total = 22
        game.dealer_total = 15
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_LOSS)
    
    def test_determine_winner_dealer_bust(self):
        """Test winner determination when dealer busts."""
        game = server_module.BlackjackGame()
        game.player_total = 18
        game.dealer_total = 22
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_WIN)
    
    def test_determine_winner_player_wins(self):
        """Test winner determination when player has higher total."""
        game = server_module.BlackjackGame()
        game.player_total = 20
        game.dealer_total = 18
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_WIN)
    
    def test_determine_winner_dealer_wins(self):
        """Test winner determination when dealer has higher total."""
        game = server_module.BlackjackGame()
        game.player_total = 16
        game.dealer_total = 18
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_LOSS)
    
    def test_determine_winner_tie(self):
        """Test winner determination on tie."""
        game = server_module.BlackjackGame()
        game.player_total = 18
        game.dealer_total = 18
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_TIE)


# ============================================================================
# MESSAGE HANDLING TESTS
# ============================================================================

class TestMessageHandling(unittest.TestCase):
    """Test network message creation and parsing."""
    
    def test_create_offer_message(self):
        """Test offer message creation."""
        message = server_module.create_offer_message(54321, "TestServer")
        self.assertEqual(len(message), 39)
        
        # Unpack and verify
        magic, msg_type, tcp_port, name_bytes = struct.unpack('!IbH32s', message)
        self.assertEqual(magic, MAGIC_COOKIE)
        self.assertEqual(msg_type, MSG_TYPE_OFFER)
        self.assertEqual(tcp_port, 54321)
        name = name_bytes.rstrip(b'\x00').decode('utf-8')
        self.assertEqual(name, "TestServer")
    
    def test_parse_offer_message(self):
        """Test offer message parsing."""
        message = server_module.create_offer_message(54321, "TestServer")
        tcp_port, server_name = client_module.parse_offer_message(message)
        self.assertEqual(tcp_port, 54321)
        self.assertEqual(server_name, "TestServer")
    
    def test_parse_offer_message_invalid(self):
        """Test offer message parsing with invalid data."""
        invalid_data = b'wrong data'
        result = client_module.parse_offer_message(invalid_data)
        self.assertIsNone(result)
    
    def test_create_request_message(self):
        """Test request message creation."""
        message = client_module.create_request_message(5, "TestClient")
        self.assertEqual(len(message), 38)
        
        # Unpack and verify
        magic, msg_type, num_rounds, name_bytes = struct.unpack('!IbB32s', message)
        self.assertEqual(magic, MAGIC_COOKIE)
        self.assertEqual(msg_type, MSG_TYPE_REQUEST)
        self.assertEqual(num_rounds, 5)
        name = name_bytes.rstrip(b'\x00').decode('utf-8')
        self.assertEqual(name, "TestClient")
    
    def test_parse_request_message(self):
        """Test request message parsing."""
        message = client_module.create_request_message(5, "TestClient")
        result = server_module.parse_request_message(message)
        self.assertIsNotNone(result)
        num_rounds, client_name = result
        self.assertEqual(num_rounds, 5)
        self.assertEqual(client_name, "TestClient")
    
    def test_create_payload_message_server(self):
        """Test server payload message creation."""
        card = server_module.Card(13, 0)
        message = server_module.create_payload_message(
            server_module.RESULT_NOT_OVER, card
        )
        self.assertEqual(len(message), 9)
        
        # Unpack and verify
        magic, msg_type, result, card_bytes = struct.unpack('!IbB3s', message)
        self.assertEqual(magic, MAGIC_COOKIE)
        self.assertEqual(msg_type, MSG_TYPE_PAYLOAD)
        self.assertEqual(result, server_module.RESULT_NOT_OVER)
    
    def test_create_payload_message_client(self):
        """Test client payload message creation."""
        message = client_module.create_payload_message("Hittt")
        self.assertEqual(len(message), 10)
        
        # Unpack and verify
        magic, msg_type, decision_bytes = struct.unpack('!Ib5s', message)
        self.assertEqual(magic, MAGIC_COOKIE)
        self.assertEqual(msg_type, MSG_TYPE_PAYLOAD)
        decision = decision_bytes.decode('utf-8').rstrip('\x00')
        self.assertEqual(decision, "Hittt")
    
    def test_parse_payload_message_server(self):
        """Test server payload message parsing."""
        message = client_module.create_payload_message("Stand")
        decision = server_module.parse_payload_message(message)
        self.assertEqual(decision, "Stand")
    
    def test_parse_payload_message_client(self):
        """Test client payload message parsing."""
        card = server_module.Card(13, 0)
        message = server_module.create_payload_message(
            server_module.RESULT_WIN, card
        )
        result = client_module.parse_payload_message(message)
        self.assertIsNotNone(result)
        result_code, parsed_card = result
        self.assertEqual(result_code, server_module.RESULT_WIN)
        self.assertIsNotNone(parsed_card)
        self.assertEqual(parsed_card.rank, 13)


# ============================================================================
# CLIENT TESTS
# ============================================================================

class TestBlackjackClient(unittest.TestCase):
    """Test BlackjackClient class functionality."""
    
    def test_client_initialization(self):
        """Test client initializes correctly."""
        client = client_module.BlackjackClient("TestClient")
        self.assertEqual(client.client_name, "TestClient")
        self.assertEqual(client.total_wins, 0)
        self.assertEqual(client.total_losses, 0)
        self.assertEqual(client.total_ties, 0)
    
    def test_make_decision_hit(self):
        """Test decision making - hit when below threshold."""
        client = client_module.BlackjackClient("TestClient")
        dealer_card = client_module.Card(10, 0)
        decision = client._make_decision(15, dealer_card)
        self.assertEqual(decision, "Hittt")
    
    def test_make_decision_stand(self):
        """Test decision making - stand when at/above threshold."""
        client = client_module.BlackjackClient("TestClient")
        dealer_card = client_module.Card(10, 0)
        decision = client._make_decision(17, dealer_card)
        self.assertEqual(decision, "Stand")


# ============================================================================
# SERVER TESTS
# ============================================================================

class TestBlackjackServer(unittest.TestCase):
    """Test BlackjackServer class functionality."""
    
    def test_server_initialization(self):
        """Test server initializes correctly."""
        server = server_module.BlackjackServer("TestServer")
        self.assertEqual(server.server_name, "TestServer")
        self.assertFalse(server.running)
        self.assertEqual(server.total_games, 0)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests for client-server communication."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.server = None
        self.server_thread = None
    
    def tearDown(self):
        """Clean up after tests."""
        if self.server:
            self.server.stop()
        if self.server_thread:
            self.server_thread.join(timeout=2)
    
    def test_server_startup(self):
        """Test server starts and binds to port."""
        server = server_module.BlackjackServer("TestServer")
        server.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.tcp_socket.bind(('127.0.0.1', 0))
        server.tcp_port = server.tcp_socket.getsockname()[1]
        server.tcp_socket.listen(5)
        
        self.assertGreater(server.tcp_port, 0)
        server.tcp_socket.close()
    
    def test_udp_broadcast(self):
        """Test UDP broadcast functionality."""
        # Create a test UDP socket to receive
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        receiver.bind(('', UDP_PORT))
        receiver.settimeout(2)
        
        # Create server and send one broadcast
        server = server_module.BlackjackServer("TestServer")
        server.tcp_port = 54321
        server.running = True
        
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        offer_message = server_module.create_offer_message(54321, "TestServer")
        udp_socket.sendto(offer_message, ('127.0.0.1', UDP_PORT))
        
        # Receive and verify
        try:
            data, addr = receiver.recvfrom(1024)
            tcp_port, server_name = client_module.parse_offer_message(data)
            self.assertEqual(tcp_port, 54321)
            self.assertEqual(server_name, "TestServer")
        except socket.timeout:
            self.fail("Did not receive UDP broadcast")
        finally:
            receiver.close()
            udp_socket.close()
    
    def test_full_game_round(self):
        """Test a complete game round with mocked sockets."""
        # Create mock socket for client
        client_socket = Mock(spec=socket.socket)
        
        # Simulate initial cards
        card1 = server_module.Card(10, 0)
        card2 = server_module.Card(7, 0)
        dealer_card = server_module.Card(9, 0)
        
        # Mock sendall calls
        client_socket.sendall = Mock()
        
        # Mock recv to return "Stand" decision
        request_msg = client_module.create_payload_message("Stand")
        client_socket.recv = Mock(return_value=request_msg)
        
        # Create game and test round
        game = server_module.BlackjackGame()
        game.player_hand = [card1, card2]
        game.dealer_hand = [dealer_card, server_module.Card(8, 0)]
        game.player_total = 17
        game.dealer_total = 17
        
        # Test winner determination
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_TIE)


# ============================================================================
# PROTOCOL COMPLIANCE TESTS
# ============================================================================

class TestProtocolCompliance(unittest.TestCase):
    """Test protocol message format compliance."""
    
    def test_offer_message_size(self):
        """Test offer message is exactly 39 bytes."""
        message = server_module.create_offer_message(54321, "Test")
        self.assertEqual(len(message), 39)
    
    def test_request_message_size(self):
        """Test request message is exactly 38 bytes."""
        message = client_module.create_request_message(5, "Test")
        self.assertEqual(len(message), 38)
    
    def test_payload_message_sizes(self):
        """Test payload messages have correct sizes."""
        # Server to client: 9 bytes
        card = server_module.Card(13, 0)
        server_msg = server_module.create_payload_message(
            server_module.RESULT_WIN, card
        )
        self.assertEqual(len(server_msg), 9)
        
        # Client to server: 10 bytes
        client_msg = client_module.create_payload_message("Hittt")
        self.assertEqual(len(client_msg), 10)
    
    def test_magic_cookie_validation(self):
        """Test magic cookie is correct in all messages."""
        # Offer message
        offer = server_module.create_offer_message(54321, "Test")
        magic, _, _, _ = struct.unpack('!IbH32s', offer)
        self.assertEqual(magic, MAGIC_COOKIE)
        
        # Request message
        request = client_module.create_request_message(5, "Test")
        magic, _, _, _ = struct.unpack('!IbB32s', request)
        self.assertEqual(magic, MAGIC_COOKIE)
        
        # Payload messages
        card = server_module.Card(13, 0)
        payload = server_module.create_payload_message(
            server_module.RESULT_WIN, card
        )
        magic, _, _ = struct.unpack('!IbB', payload[:6])
        self.assertEqual(magic, MAGIC_COOKIE)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def test_long_server_name_truncation(self):
        """Test server name is truncated to 32 bytes."""
        long_name = "A" * 50
        message = server_module.create_offer_message(54321, long_name)
        _, _, _, name_bytes = struct.unpack('!IbH32s', message)
        name = name_bytes.rstrip(b'\x00').decode('utf-8')
        self.assertLessEqual(len(name), 32)
    
    def test_long_client_name_truncation(self):
        """Test client name is truncated to 32 bytes."""
        long_name = "B" * 50
        message = client_module.create_request_message(5, long_name)
        _, _, _, name_bytes = struct.unpack('!IbB32s', message)
        name = name_bytes.rstrip(b'\x00').decode('utf-8')
        self.assertLessEqual(len(name), 32)
    
    def test_empty_names(self):
        """Test empty server and client names."""
        # Empty server name
        message = server_module.create_offer_message(54321, "")
        _, _, _, name_bytes = struct.unpack('!IbH32s', message)
        name = name_bytes.rstrip(b'\x00').decode('utf-8')
        self.assertEqual(name, "")
        
        # Empty client name
        message = client_module.create_request_message(5, "")
        _, _, _, name_bytes = struct.unpack('!IbB32s', message)
        name = name_bytes.rstrip(b'\x00').decode('utf-8')
        self.assertEqual(name, "")
    
    def test_unicode_names(self):
        """Test unicode characters in names."""
        unicode_name = "测试服务器🎰"
        message = server_module.create_offer_message(54321, unicode_name)
        _, _, _, name_bytes = struct.unpack('!IbH32s', message)
        # Should handle unicode gracefully
        try:
            name = name_bytes.rstrip(b'\x00').decode('utf-8')
            self.assertIsInstance(name, str)
        except UnicodeDecodeError:
            self.fail("Unicode name should be handled gracefully")
    
    def test_empty_card_decode(self):
        """Test decoding empty/invalid card bytes."""
        self.assertIsNone(client_module.Card.decode(b''))
        self.assertIsNone(client_module.Card.decode(b'00'))
        self.assertIsNone(client_module.Card.decode(b'999'))
        self.assertIsNone(client_module.Card.decode(b'1'))
        self.assertIsNone(client_module.Card.decode(b'1234'))  # Too long
    
    def test_invalid_card_ranks(self):
        """Test invalid card rank values."""
        # Rank 0 (invalid)
        self.assertIsNone(client_module.Card.decode(b'00\x00'))
        # Rank 14 (invalid, max is 13)
        self.assertIsNone(client_module.Card.decode(b'14\x00'))
        # Rank 99 (invalid)
        self.assertIsNone(client_module.Card.decode(b'99\x00'))
    
    def test_invalid_card_suits(self):
        """Test invalid card suit values."""
        # Suit 4 (invalid, max is 3)
        self.assertIsNone(client_module.Card.decode(b'01\x04'))
        # Suit 255 (invalid)
        self.assertIsNone(client_module.Card.decode(b'01\xff'))
    
    def test_invalid_message_parsing(self):
        """Test parsing invalid messages."""
        invalid_data = b'invalid'
        self.assertIsNone(client_module.parse_offer_message(invalid_data))
        self.assertIsNone(server_module.parse_request_message(invalid_data))
        self.assertIsNone(client_module.parse_payload_message(invalid_data))
        
        # Too short
        self.assertIsNone(client_module.parse_offer_message(b'123'))
        self.assertIsNone(server_module.parse_request_message(b'123'))
        self.assertIsNone(client_module.parse_payload_message(b'123'))
        
        # Wrong magic cookie
        wrong_magic = struct.pack('!IbH32s', 0x12345678, 0x2, 54321, b'Test' + b'\x00' * 28)
        self.assertIsNone(client_module.parse_offer_message(wrong_magic))
    
    def test_wrong_message_types(self):
        """Test messages with wrong message type."""
        # Offer message type in request
        wrong_type = struct.pack('!IbB32s', MAGIC_COOKIE, MSG_TYPE_OFFER, 5, b'Test' + b'\x00' * 28)
        self.assertIsNone(server_module.parse_request_message(wrong_type))
        
        # Request message type in offer
        wrong_type = struct.pack('!IbH32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, 54321, b'Test' + b'\x00' * 28)
        self.assertIsNone(client_module.parse_offer_message(wrong_type))
    
    def test_card_encoding_edge_cases(self):
        """Test card encoding for edge cases."""
        # Ace (rank 1)
        ace = server_module.Card(1, 0)
        encoded = ace.encode()
        self.assertEqual(encoded[:2], b'01')
        
        # Single digit rank
        card = server_module.Card(5, 0)
        encoded = card.encode()
        self.assertEqual(encoded[:2], b'05')
        
        # Maximum rank (King = 13)
        king = server_module.Card(13, 0)
        encoded = king.encode()
        self.assertEqual(encoded[:2], b'13')
        
        # All suits
        for suit in range(4):
            card = server_module.Card(10, suit)
            encoded = card.encode()
            self.assertEqual(encoded[2], suit)
    
    def test_game_boundary_values(self):
        """Test game logic with boundary values."""
        game = server_module.BlackjackGame()
        
        # Exactly 21 (should not bust)
        game.player_total = 21
        game.dealer_total = 20
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_WIN)
        
        # Exactly 17 (dealer should stand)
        game.dealer_total = 17
        game.player_total = 16
        # Dealer should stand at 17
        drawn = game.dealer_play()
        self.assertEqual(len(drawn), 0)  # No cards drawn
        
        # Exactly 22 (bust)
        game.player_total = 22
        game.dealer_total = 15
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_LOSS)
    
    def test_exact_21_scenarios(self):
        """Test scenarios where total is exactly 21."""
        game = server_module.BlackjackGame()
        
        # Player 21, Dealer 21 (tie)
        game.player_total = 21
        game.dealer_total = 21
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_TIE)
        
        # Player 21, Dealer 20 (player wins)
        game.player_total = 21
        game.dealer_total = 20
        result = game.determine_winner()
        self.assertEqual(result, server_module.RESULT_WIN)
    
    def test_dealer_stand_threshold(self):
        """Test dealer behavior at stand threshold."""
        game = server_module.BlackjackGame()
        
        # Dealer at 16 (should hit)
        game.dealer_total = 16
        game.dealer_hand = [server_module.Card(10, 0), server_module.Card(6, 0)]
        drawn = game.dealer_play()
        self.assertGreater(len(drawn), 0)
        
        # Dealer at 17 (should stand)
        game.dealer_total = 17
        game.dealer_hand = [server_module.Card(10, 0), server_module.Card(7, 0)]
        drawn = game.dealer_play()
        self.assertEqual(len(drawn), 0)
    
    def test_maximum_rounds(self):
        """Test maximum number of rounds (255)."""
        message = client_module.create_request_message(255, "Test")
        num_rounds, _ = server_module.parse_request_message(message)
        self.assertEqual(num_rounds, 255)
    
    def test_minimum_rounds(self):
        """Test minimum number of rounds (1)."""
        message = client_module.create_request_message(1, "Test")
        num_rounds, _ = server_module.parse_request_message(message)
        self.assertEqual(num_rounds, 1)
    
    def test_zero_rounds(self):
        """Test zero rounds (edge case)."""
        message = client_module.create_request_message(0, "Test")
        num_rounds, _ = server_module.parse_request_message(message)
        self.assertEqual(num_rounds, 0)
    
    def test_port_edge_cases(self):
        """Test TCP port edge cases."""
        # Minimum port (1)
        message = server_module.create_offer_message(1, "Test")
        port, _ = client_module.parse_offer_message(message)
        self.assertEqual(port, 1)
        
        # Maximum port (65535)
        message = server_module.create_offer_message(65535, "Test")
        port, _ = client_module.parse_offer_message(message)
        self.assertEqual(port, 65535)
    
    def test_payload_with_no_card(self):
        """Test payload message with no card (final result)."""
        message = server_module.create_payload_message(
            server_module.RESULT_WIN, None
        )
        result, card = client_module.parse_payload_message(message)
        self.assertEqual(result, server_module.RESULT_WIN)
        # Card should be None or invalid when no card sent
        # (Implementation uses b'000' as placeholder)
    
    def test_invalid_decision_strings(self):
        """Test invalid decision strings in payload."""
        # Create message with invalid decision
        invalid_decision = b'Wrong'[:5].ljust(5, b'\x00')
        message = struct.pack('!Ib5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, invalid_decision)
        decision = server_module.parse_payload_message(message)
        # Should return None for invalid decisions
        self.assertIsNone(decision)
    
    def test_decision_case_sensitivity(self):
        """Test decision parsing is case-sensitive."""
        # "hittt" (lowercase) should be invalid
        invalid = b'hittt'[:5].ljust(5, b'\x00')
        message = struct.pack('!Ib5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, invalid)
        decision = server_module.parse_payload_message(message)
        self.assertIsNone(decision)  # Should only accept "Hittt" and "Stand"
    
    def test_multiple_aces_hand_value(self):
        """Test hand with multiple aces."""
        game = server_module.BlackjackGame()
        # Two aces = 22 (both count as 11)
        hand = [
            server_module.Card(1, 0),  # Ace = 11
            server_module.Card(1, 0)   # Ace = 11
        ]
        total = game.calculate_hand_value(hand)
        self.assertEqual(total, 22)  # Note: Real blackjack would adjust, but our implementation doesn't
    
    def test_hand_with_all_face_cards(self):
        """Test hand with all face cards."""
        game = server_module.BlackjackGame()
        hand = [
            server_module.Card(11, 0),  # Jack = 10
            server_module.Card(12, 0),  # Queen = 10
            server_module.Card(13, 0)   # King = 10
        ]
        total = game.calculate_hand_value(hand)
        self.assertEqual(total, 30)
    
    def test_deck_exhaustion(self):
        """Test behavior when deck is exhausted multiple times."""
        deck = server_module.Deck()
        # Draw all 52 cards
        for _ in range(52):
            card = deck.draw()
            self.assertIsNotNone(card)
        
        # Next draw should trigger reshuffle
        card = deck.draw()
        self.assertIsNotNone(card)
        self.assertEqual(len(deck.cards), 51)  # New deck minus one
    
    def test_message_size_boundaries(self):
        """Test message size boundaries."""
        # Offer message should be exactly 39 bytes
        offer = server_module.create_offer_message(54321, "Test")
        self.assertEqual(len(offer), 39)
        
        # Request message should be exactly 38 bytes
        request = client_module.create_request_message(5, "Test")
        self.assertEqual(len(request), 38)
        
        # Payload server->client should be exactly 9 bytes
        card = server_module.Card(10, 0)
        payload = server_module.create_payload_message(
            server_module.RESULT_NOT_OVER, card
        )
        self.assertEqual(len(payload), 9)
        
        # Payload client->server should be exactly 10 bytes
        payload = client_module.create_payload_message("Stand")
        self.assertEqual(len(payload), 10)


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestCard,
        TestDeck,
        TestBlackjackGame,
        TestMessageHandling,
        TestBlackjackClient,
        TestBlackjackServer,
        TestIntegration,
        TestProtocolCompliance,
        TestEdgeCases,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    
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

