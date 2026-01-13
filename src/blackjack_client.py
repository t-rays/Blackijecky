#!/usr/bin/env python3
"""
Blackjack Client Implementation
Intro to Computer Networks 2025 Hackathon

This client discovers blackjack servers via UDP broadcasts and connects to play games.
It implements a simple strategy and tracks game statistics.
"""

import socket
import struct
import sys
import time
import argparse
from typing import Optional, Tuple, List
from tcp_utils import recv_exact

# ============================================================================
# CONSTANTS
# ============================================================================

# Network Protocol Constants
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4

# UDP discovery settings
UDP_PORT = 13122
DISCOVERY_TIMEOUT = 5  # seconds to wait for offers

# Payload message constants
RESULT_NOT_OVER = 0x0
RESULT_TIE = 0x1
RESULT_LOSS = 0x2
RESULT_WIN = 0x3

# Card constants
SUITS = ['♥', '♦', '♣', '♠']  # Heart, Diamond, Club, Spade
RANK_NAMES = ['', 'A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

# Game constants
BUST_THRESHOLD = 21
STAND_THRESHOLD = 17  # Simple strategy: stand on 17+

# Client configuration
CLIENT_NAME = "DragonLion"  # Change this to your team name


# ============================================================================
# CARD REPRESENTATION
# ============================================================================

class Card:
    """Represents a playing card received from the server."""
    
    def __init__(self, rank: int, suit: int):
        """
        Initialize a card.
        
        Args:
            rank: Card rank (1-13)
            suit: Card suit (0-3)
        """
        self.rank = rank
        self.suit = suit
    
    def get_value(self) -> int:
        """
        Get the blackjack value of the card.
        For simplicity, Aces are valued as 1 (as allowed by forum Q&A).
        
        Returns:
            Card value (Ace=1, Face cards=10, others=rank)
        """
        if self.rank == 1:  # Ace
            return 1
        elif self.rank >= 11:  # Jack, Queen, King
            return 10
        else:
            return self.rank
    
    @staticmethod
    def decode(card_bytes: bytes) -> Optional['Card']:
        """
        Decode a card from 3 bytes.
        
        Args:
            card_bytes: 3-byte card representation
            
        Returns:
            Card object or None if invalid
        """
        if len(card_bytes) != 3:
            return None
        
        try:
            rank_str = card_bytes[:2].decode('ascii')
            rank = int(rank_str)
            suit = card_bytes[2]
            
            if 1 <= rank <= 13 and 0 <= suit <= 3:
                return Card(rank, suit)
        except (ValueError, UnicodeDecodeError):
            pass
        
        return None
    
    def __str__(self) -> str:
        """String representation of the card."""
        return f"{RANK_NAMES[self.rank]}{SUITS[self.suit]}"


# ============================================================================
# NETWORK MESSAGE HANDLING
# ============================================================================

def parse_offer_message(data: bytes) -> Optional[Tuple[int, str]]:
    """
    Parse a UDP offer message from server.
    
    Args:
        data: Raw message bytes
        
    Returns:
        Tuple of (tcp_port, server_name) or None if invalid
    """
    if len(data) < 39:
        return None
    
    try:
        magic, msg_type, tcp_port, name_bytes = struct.unpack('!IbH32s', data[:39])
        
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_OFFER:
            return None
        
        server_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='ignore')
        return (tcp_port, server_name)
    
    except struct.error:
        return None


def create_request_message(num_rounds: int, client_name: str) -> bytes:
    """
    Create a TCP request message.
    
    Args:
        num_rounds: Number of rounds to play
        client_name: Name of the client (max 32 chars)
        
    Returns:
        Packed request message as bytes
    """
    # Truncate or pad client name to exactly 32 bytes
    name_bytes = client_name.encode('utf-8')[:32].ljust(32, b'\x00')
    
    # Pack: Magic cookie (4B), Message type (1B), Num rounds (1B), Name (32B)
    return struct.pack('!IbB32s', MAGIC_COOKIE, MSG_TYPE_REQUEST, num_rounds, name_bytes)


def create_payload_message(decision: str) -> bytes:
    """
    Create a TCP payload message (client to server).
    
    Args:
        decision: "Hitt" or "Stand" (will be padded to 5 bytes)
        
    Returns:
        Packed payload message as bytes
    """
    # Ensure decision is exactly 5 bytes
    decision_bytes = decision.encode('utf-8')[:5].ljust(5, b'\x00')
    
    # Pack: Magic cookie (4B), Message type (1B), Decision (5B)
    return struct.pack('!Ib5s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision_bytes)


def parse_payload_message(data: bytes) -> Optional[Tuple[int, Optional[Card]]]:
    """
    Parse a TCP payload message from server.
    
    Args:
        data: Raw message bytes
        
    Returns:
        Tuple of (result, card) or None if invalid
    """
    if len(data) < 9:
        return None
    
    try:
        magic, msg_type, result, card_bytes = struct.unpack('!IbB3s', data[:9])
        
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return None
        
        card = Card.decode(card_bytes)
        return (result, card)
    
    except struct.error:
        return None


# ============================================================================
# CLIENT GAME LOGIC
# ============================================================================

def calculate_hand_value(hand: List[Card]) -> int:
    """
    Calculate the total value of a hand.
    For simplicity, Aces are valued as 1 (as allowed by forum Q&A).
    
    Args:
        hand: List of Card objects
        
    Returns:
        Total value of the hand
    """
    return sum(card.get_value() for card in hand)

class BlackjackClient:
    """Main client class that discovers servers and plays games."""
    
    def __init__(self, client_name: str):
        """
        Initialize the client.
        
        Args:
            client_name: Name to send to servers
        """
        self.client_name = client_name
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0
        self.total_rounds = 0
    
    def discover_server(self) -> Optional[Tuple[str, int, str]]:
        """
        Listen for UDP offer broadcasts and return first valid offer.
        
        Returns:
            Tuple of (server_ip, tcp_port, server_name) or None if timeout
        """
        print("Client started, listening for offer requests...")
        
        # Create UDP socket for receiving broadcasts
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        udp_socket.bind(('', UDP_PORT))
        udp_socket.settimeout(DISCOVERY_TIMEOUT)
        
        try:
            while True:
                data, address = udp_socket.recvfrom(1024)
                server_ip = address[0]
                
                parsed = parse_offer_message(data)
                if parsed:
                    tcp_port, server_name = parsed
                    print(f"Received offer from {server_name} at {server_ip}")
                    udp_socket.close()
                    return (server_ip, tcp_port, server_name)
        
        except socket.timeout:
            print("No offers received within timeout period")
            udp_socket.close()
            return None
        except Exception as e:
            print(f"Error during discovery: {e}")
            udp_socket.close()
            return None
    
    def play_session(self, server_ip: str, tcp_port: int, num_rounds: int) -> bool:
        """
        Connect to server and play the requested number of rounds.
        
        Args:
            server_ip: Server IP address
            tcp_port: Server TCP port
            num_rounds: Number of rounds to play
            
        Returns:
            True if session completed successfully, False otherwise
        """
        tcp_socket = None
        
        try:
            # Connect to server via TCP
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.settimeout(30)  # 30 second timeout
            tcp_socket.connect((server_ip, tcp_port))
            
            print(f"Connected to server at {server_ip}:{tcp_port}")
            
            # Send request message
            request_msg = create_request_message(num_rounds, self.client_name)
            tcp_socket.sendall(request_msg)
            
            # Play rounds
            session_wins = 0
            session_losses = 0
            session_ties = 0
            
            for round_num in range(1, num_rounds + 1):
                print(f"\n{'='*60}")
                print(f"Round {round_num}/{num_rounds}")
                print(f"{'='*60}")
                
                result = self._play_round(tcp_socket)
                
                if result == RESULT_WIN:
                    session_wins += 1
                    print("🎉 You WIN this round!")
                elif result == RESULT_LOSS:
                    session_losses += 1
                    print("💔 You LOSE this round.")
                elif result == RESULT_TIE:
                    session_ties += 1
                    print("🤝 It's a TIE!")
                else:
                    print("❌ Round ended unexpectedly")
                    return False
            
            # Update overall statistics
            self.total_wins += session_wins
            self.total_losses += session_losses
            self.total_ties += session_ties
            self.total_rounds += num_rounds
            
            # Calculate win rate
            win_rate = (session_wins / num_rounds * 100) if num_rounds > 0 else 0
            
            print(f"\n{'='*60}")
            print(f"Finished playing {num_rounds} rounds, win rate: {win_rate:.1f}%")
            print(f"Session results: {session_wins}W-{session_losses}L-{session_ties}T")
            print(f"Overall stats: {self.total_wins}W-{self.total_losses}L-{self.total_ties}T ({self.total_rounds} total)")
            print(f"{'='*60}\n")
            
            return True
        
        except socket.timeout:
            print("Connection timeout")
            return False
        except Exception as e:
            print(f"Error during game session: {e}")
            return False
        finally:
            if tcp_socket:
                tcp_socket.close()
    
    def _play_round(self, tcp_socket: socket.socket) -> int:
        """
        Play a single round of blackjack.
        
        Args:
            tcp_socket: Connected TCP socket
            
        Returns:
            Result code (RESULT_WIN, RESULT_LOSS, RESULT_TIE, or -1 on error)
        """
        player_hand: List[Card] = []
        dealer_hand: List[Card] = []
        
        try:
            # Receive initial cards: 2 for player, 1 visible for dealer
            # Each card message is exactly 9 bytes
            for i in range(3):
                data = recv_exact(tcp_socket, 9)
                if len(data) < 9:
                    print("Connection closed during initial deal")
                    return -1
                parsed = parse_payload_message(data)
                
                if not parsed:
                    print("Invalid payload message")
                    return -1
                
                result, card = parsed
                
                if card:
                    if i < 2:
                        player_hand.append(card)
                        print(f"Your card: {card}")
                    else:
                        dealer_hand.append(card)
                        print(f"Dealer's visible card: {card}")
            
            # Calculate player's total (with flexible Ace handling)
            player_total = calculate_hand_value(player_hand)
            print(f"Your total: {player_total}")
            
            # Player's turn - use simple strategy
            while player_total < STAND_THRESHOLD:
                decision = self._make_decision(player_total, dealer_hand[0])
                print(f"\nYour decision: {decision}")
                
                # Send decision to server
                tcp_socket.sendall(create_payload_message(decision))
                
                if decision == "Stand":
                    break
                
                # Receive result of hit (exactly 9 bytes)
                data = recv_exact(tcp_socket, 9)
                if len(data) < 9:
                    print("Connection closed during hit response")
                    return -1
                parsed = parse_payload_message(data)
                
                if not parsed:
                    print("Invalid response from server")
                    return -1
                
                result, card = parsed
                
                if result == RESULT_LOSS:
                    # Busted
                    if card:
                        player_hand.append(card)
                        player_total = calculate_hand_value(player_hand)
                        print(f"Drew: {card}")
                        print(f"Your total: {player_total}")
                        print(f"BUST! You went over 21.")
                    return RESULT_LOSS
                
                if card:
                    player_hand.append(card)
                    player_total = calculate_hand_value(player_hand)
                    print(f"Drew: {card}")
                    print(f"Your total: {player_total}")
            
            # If we stood, send Stand decision
            if player_total >= STAND_THRESHOLD:
                decision = "Stand"
                print(f"\nYour decision: {decision}")
                tcp_socket.sendall(create_payload_message(decision))
            
            # Receive dealer's cards
            print(f"\nDealer's turn:")
            dealer_total = calculate_hand_value(dealer_hand)
            
            while True:
                # Receive dealer card (exactly 9 bytes)
                data = recv_exact(tcp_socket, 9)
                if len(data) < 9:
                    print("Connection closed during dealer turn")
                    return -1
                parsed = parse_payload_message(data)
                
                if not parsed:
                    print("Invalid response from server")
                    return -1
                
                result, card = parsed
                
                if result != RESULT_NOT_OVER:
                    # Round is over
                    print(f"\nFinal totals: You {player_total} vs Dealer {dealer_total}")
                    return result
                
                if card:
                    dealer_hand.append(card)
                    dealer_total = calculate_hand_value(dealer_hand)
                    print(f"Dealer draws: {card} (Total: {dealer_total})")
                    
                    if dealer_total > BUST_THRESHOLD:
                        print(f"Dealer BUSTS with {dealer_total}!")
        
        except Exception as e:
            print(f"Error during round: {e}")
            return -1
    
    def _make_decision(self, player_total: int, dealer_card: Card) -> str:
        """
        Decide whether to hit or stand based on simple strategy.
        
        Args:
            player_total: Current player total
            dealer_card: Dealer's visible card
            
        Returns:
            "Hitt" or "Stand"
        """
        # Simple strategy: hit if total < 17, stand if >= 17
        if player_total < STAND_THRESHOLD:
            return "Hitt"
        else:
            return "Stand"
    
    def run_forever(self):
        """
        Main loop: discover server, play, repeat.
        """
        print(f"{'='*60}")
        print(f"Blackjack Client - {self.client_name}")
        print(f"{'='*60}\n")
        
        while True:
            try:
                # Get number of rounds from user
                num_rounds = self._get_num_rounds()
                
                if num_rounds <= 0:
                    print("Exiting...")
                    break
                
                # Discover server
                server_info = self.discover_server()
                
                if not server_info:
                    print("Failed to discover server. Retrying...\n")
                    time.sleep(2)
                    continue
                
                server_ip, tcp_port, server_name = server_info
                
                # Play session
                success = self.play_session(server_ip, tcp_port, num_rounds)
                
                if not success:
                    print("Session failed. Returning to discovery...\n")
                    time.sleep(1)
            
            except KeyboardInterrupt:
                print("\n\nExiting client...")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                time.sleep(2)
    
    def _get_num_rounds(self) -> int:
        """
        Prompt user for number of rounds to play.
        
        Returns:
            Number of rounds (0 to exit)
        """
        while True:
            try:
                user_input = input("\nHow many rounds would you like to play? (0 to exit): ")
                num_rounds = int(user_input)
                
                if num_rounds < 0:
                    print("Please enter a non-negative number.")
                    continue
                
                if num_rounds > 255:
                    print("Maximum 255 rounds allowed.")
                    continue
                
                return num_rounds
            
            except ValueError:
                print("Please enter a valid number.")
            except EOFError:
                return 0


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the client application."""
    parser = argparse.ArgumentParser(description='Blackjack Client')
    parser.add_argument('--name', '-n', type=str, default=None,
                        help='Client name (will prompt if not provided)')
    args = parser.parse_args()
    
    # Get client name from argument, prompt, or use default
    client_name = args.name
    if not client_name:
        try:
            client_name = input(f"Enter client name (default: {CLIENT_NAME}): ").strip()
            if not client_name:
                client_name = CLIENT_NAME
        except (EOFError, KeyboardInterrupt):
            client_name = CLIENT_NAME
            print(f"\nUsing default client name: {client_name}")
    
    client = BlackjackClient(client_name)
    client.run_forever()


if __name__ == "__main__":
    main()

