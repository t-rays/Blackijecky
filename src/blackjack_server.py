#!/usr/bin/env python3
"""
Blackjack Server Implementation
Intro to Computer Networks 2025 Hackathon

This server hosts a simplified Blackjack game and handles multiple concurrent clients.
It broadcasts UDP offer messages and manages TCP game sessions.
"""

import socket
import struct
import threading
import time
import random
from typing import List, Tuple, Optional
from tcp_utils import recv_exact

# ============================================================================
# CONSTANTS
# ============================================================================

# Network Protocol Constants
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4

# UDP broadcast settings
UDP_PORT = 13122
BROADCAST_INTERVAL = 1  # seconds

# Payload message constants
RESULT_NOT_OVER = 0x0
RESULT_TIE = 0x1
RESULT_LOSS = 0x2
RESULT_WIN = 0x3

# Card constants
SUITS = ['♥', '♦', '♣', '♠']  # Heart, Diamond, Club, Spade
SUIT_CODES = {'H': 0, 'D': 1, 'C': 2, 'S': 3}
RANK_NAMES = ['', 'A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

# Game constants
DEALER_STAND_THRESHOLD = 17
BUST_THRESHOLD = 21

# Server configuration
SERVER_NAME = "DragonLion"  # Change this to your team name
TCP_PORT = 0  # Will be assigned dynamically


# ============================================================================
# CARD AND DECK MANAGEMENT
# ============================================================================

class Card:
    """Represents a playing card with rank and suit."""
    
    def __init__(self, rank: int, suit: int):
        """
        Initialize a card.
        
        Args:
            rank: Card rank (1-13, where 1=Ace, 11=Jack, 12=Queen, 13=King)
            suit: Card suit (0-3, representing H, D, C, S)
        """
        self.rank = rank
        self.suit = suit
    
    def get_value(self) -> int:
        """
        Get the blackjack value of the card.
        
        Returns:
            Card value (Ace=11, Face cards=10, others=rank)
        """
        if self.rank == 1:  # Ace
            return 11
        elif self.rank >= 11:  # Jack, Queen, King
            return 10
        else:
            return self.rank
    
    def encode(self) -> bytes:
        """
        Encode card as 3 bytes: 2 bytes for rank, 1 byte for suit.
        
        Returns:
            3-byte representation of the card
        """
        # Encode rank as 2-digit string in first 2 bytes
        rank_str = f"{self.rank:02d}"
        return rank_str.encode('ascii') + bytes([self.suit])
    
    def __str__(self) -> str:
        """String representation of the card."""
        return f"{RANK_NAMES[self.rank]}{SUITS[self.suit]}"


class Deck:
    """Represents a deck of 52 playing cards."""
    
    def __init__(self):
        """Initialize and shuffle a new deck."""
        self.cards: List[Card] = []
        self.reset()
    
    def reset(self):
        """Create a fresh deck with all 52 cards and shuffle it."""
        self.cards = [Card(rank, suit) for rank in range(1, 14) for suit in range(4)]
        random.shuffle(self.cards)
    
    def draw(self) -> Optional[Card]:
        """
        Draw a card from the deck.
        
        Returns:
            A Card object, or None if deck is empty
        """
        if not self.cards:
            self.reset()  # Auto-reshuffle if deck runs out
        return self.cards.pop() if self.cards else None


# ============================================================================
# GAME LOGIC
# ============================================================================

class BlackjackGame:
    """Manages the logic for a single blackjack game session."""
    
    def __init__(self):
        """Initialize a new game session."""
        self.deck = Deck()
        self.player_hand: List[Card] = []
        self.dealer_hand: List[Card] = []
        self.player_total = 0
        self.dealer_total = 0
    
    def calculate_hand_value(self, hand: List[Card]) -> int:
        """
        Calculate the total value of a hand.
        
        Args:
            hand: List of Card objects
            
        Returns:
            Total value of the hand
        """
        return sum(card.get_value() for card in hand)
    
    def deal_initial_cards(self) -> Tuple[Card, Card, Card]:
        """
        Deal initial cards: 2 to player, 2 to dealer.
        
        Returns:
            Tuple of (player_card1, player_card2, dealer_visible_card)
        """
        self.player_hand = [self.deck.draw(), self.deck.draw()]
        self.dealer_hand = [self.deck.draw(), self.deck.draw()]
        
        self.player_total = self.calculate_hand_value(self.player_hand)
        self.dealer_total = self.calculate_hand_value(self.dealer_hand)
        
        return (self.player_hand[0], self.player_hand[1], self.dealer_hand[0])
    
    def player_hit(self) -> Tuple[Card, int, bool]:
        """
        Player requests another card.
        
        Returns:
            Tuple of (new_card, new_total, is_bust)
        """
        new_card = self.deck.draw()
        self.player_hand.append(new_card)
        self.player_total = self.calculate_hand_value(self.player_hand)
        is_bust = self.player_total > BUST_THRESHOLD
        
        return (new_card, self.player_total, is_bust)
    
    def dealer_play(self) -> List[Card]:
        """
        Execute dealer's turn according to rules (hit until 17+).
        
        Returns:
            List of cards drawn by dealer (excluding initial cards)
        """
        drawn_cards = []
        
        while self.dealer_total < DEALER_STAND_THRESHOLD:
            new_card = self.deck.draw()
            self.dealer_hand.append(new_card)
            drawn_cards.append(new_card)
            self.dealer_total = self.calculate_hand_value(self.dealer_hand)
        
        return drawn_cards
    
    def determine_winner(self) -> int:
        """
        Determine the winner of the round.
        
        Returns:
            RESULT_WIN, RESULT_LOSS, or RESULT_TIE
        """
        if self.player_total > BUST_THRESHOLD:
            return RESULT_LOSS
        elif self.dealer_total > BUST_THRESHOLD:
            return RESULT_WIN
        elif self.player_total > self.dealer_total:
            return RESULT_WIN
        elif self.dealer_total > self.player_total:
            return RESULT_LOSS
        else:
            return RESULT_TIE


# ============================================================================
# NETWORK MESSAGE HANDLING
# ============================================================================

def create_offer_message(tcp_port: int, server_name: str) -> bytes:
    """
    Create a UDP offer message.
    
    Args:
        tcp_port: TCP port where server accepts connections
        server_name: Name of the server (max 32 chars)
        
    Returns:
        Packed offer message as bytes
    """
    # Truncate or pad server name to exactly 32 bytes
    name_bytes = server_name.encode('utf-8')[:32].ljust(32, b'\x00')
    
    # Pack: Magic cookie (4B), Message type (1B), TCP port (2B), Name (32B)
    return struct.pack('!IbH32s', MAGIC_COOKIE, MSG_TYPE_OFFER, tcp_port, name_bytes)


def parse_request_message(data: bytes) -> Optional[Tuple[int, str]]:
    """
    Parse a TCP request message from client.
    
    Args:
        data: Raw message bytes
        
    Returns:
        Tuple of (num_rounds, client_name) or None if invalid
    """
    if len(data) < 38:
        return None
    
    try:
        magic, msg_type, num_rounds, name_bytes = struct.unpack('!IbB32s', data[:38])
        
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
            return None
        
        client_name = name_bytes.rstrip(b'\x00').decode('utf-8', errors='ignore')
        return (num_rounds, client_name)
    
    except struct.error:
        return None


def create_payload_message(result: int, card: Optional[Card]) -> bytes:
    """
    Create a TCP payload message (server to client).
    
    Args:
        result: Round result code (RESULT_WIN, RESULT_LOSS, RESULT_TIE, RESULT_NOT_OVER)
        card: Card to send, or None
        
    Returns:
        Packed payload message as bytes
    """
    if card:
        card_bytes = card.encode()
    else:
        card_bytes = b'000'  # Placeholder when no card
    
    # Pack: Magic cookie (4B), Message type (1B), Result (1B), Card (3B)
    return struct.pack('!IbB3s', MAGIC_COOKIE, MSG_TYPE_PAYLOAD, result, card_bytes)


def parse_payload_message(data: bytes) -> Optional[str]:
    """
    Parse a TCP payload message from client.
    
    Args:
        data: Raw message bytes
        
    Returns:
        Player decision ("Hitt" or "Stand") or None if invalid
    """
    if len(data) < 10:
        return None
    
    try:
        magic, msg_type, decision_bytes = struct.unpack('!Ib5s', data[:10])
        
        if magic != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
            return None
        
        decision = decision_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
        return decision if decision in ["Hitt", "Stand"] else None
    
    except struct.error:
        return None


# ============================================================================
# SERVER IMPLEMENTATION
# ============================================================================

class BlackjackServer:
    """Main server class that handles UDP broadcasts and TCP game sessions."""
    
    def __init__(self, server_name: str):
        """
        Initialize the server.
        
        Args:
            server_name: Name to broadcast to clients
        """
        self.server_name = server_name
        self.tcp_socket = None
        self.tcp_port = 0
        self.udp_socket = None
        self.running = False
        self.stats_lock = threading.Lock()
        self.total_games = 0
        self.total_wins = 0
        self.total_losses = 0
        self.total_ties = 0
    
    def start(self):
        """Start the server: set up sockets and begin broadcasting."""
        self.running = True
        
        # Set up TCP socket for game connections
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('', 0))  # Bind to any available port
        self.tcp_socket.listen(5)
        self.tcp_port = self.tcp_socket.getsockname()[1]
        
        # Get server IP address
        # Try multiple methods to get the IP address
        server_ip = None
        try:
            # Method 1: Get IP from hostname
            hostname = socket.gethostname()
            if hostname:
                server_ip = socket.gethostbyname(hostname)
        except (socket.gaierror, socket.herror):
            pass
        
        if not server_ip:
            try:
                # Method 2: Connect to external address to get local IP
                # This doesn't actually connect, just determines the route
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    s.connect(('8.8.8.8', 80))
                    server_ip = s.getsockname()[0]
                except:
                    pass
                finally:
                    s.close()
            except:
                pass
        
        if not server_ip:
            # Method 3: Use socket's bound address
            server_ip = self.tcp_socket.getsockname()[0]
            if server_ip == '0.0.0.0':
                # If bound to all interfaces, try to get a real IP
                server_ip = '127.0.0.1'  # Fallback to localhost
        
        print(f"Server started, listening on IP address {server_ip}")
        print(f"TCP port: {self.tcp_port}")
        print(f"Server name: {self.server_name}")
        print("=" * 60)
        
        # Start UDP broadcast thread
        broadcast_thread = threading.Thread(target=self._broadcast_offers, daemon=True)
        broadcast_thread.start()
        
        # Accept client connections
        self._accept_clients()
    
    def _broadcast_offers(self):
        """Broadcast UDP offer messages every second."""
        # Set up UDP broadcast socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        offer_message = create_offer_message(self.tcp_port, self.server_name)
        
        while self.running:
            try:
                self.udp_socket.sendto(offer_message, ('<broadcast>', UDP_PORT))
                time.sleep(BROADCAST_INTERVAL)
            except Exception as e:
                print(f"Broadcast error: {e}")
    
    def _accept_clients(self):
        """Accept and handle incoming TCP client connections."""
        print("Waiting for clients to connect...")
        
        while self.running:
            try:
                client_socket, client_address = self.tcp_socket.accept()
                print(f"\n[NEW CONNECTION] Client connected from {client_address}")
                
                # Handle each client in a separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    print(f"Error accepting client: {e}")
    
    def _handle_client(self, client_socket: socket.socket, client_address: Tuple):
        """
        Handle a single client connection and play multiple rounds.
        
        Args:
            client_socket: Connected client socket
            client_address: Client's address tuple
        """
        client_socket.settimeout(30)  # 30 second timeout
        
        try:
            # Receive request message (exactly 38 bytes)
            request_data = recv_exact(client_socket, 38)
            if len(request_data) < 38:
                print(f"[{client_address}] Connection closed during request")
                return
            parsed = parse_request_message(request_data)
            
            if not parsed:
                print(f"[{client_address}] Invalid request message")
                return
            
            num_rounds, client_name = parsed
            print(f"[{client_address}] {client_name} wants to play {num_rounds} rounds")
            
            # Play the requested number of rounds
            client_wins = 0
            client_losses = 0
            client_ties = 0
            
            for round_num in range(1, num_rounds + 1):
                print(f"\n--- Round {round_num}/{num_rounds} with {client_name} ---")
                
                result = self._play_round(client_socket, client_name)
                
                if result == RESULT_WIN:
                    client_wins += 1
                    print(f"Round {round_num}: {client_name} WINS!")
                elif result == RESULT_LOSS:
                    client_losses += 1
                    print(f"Round {round_num}: {client_name} loses.")
                elif result == RESULT_TIE:
                    client_ties += 1
                    print(f"Round {round_num}: TIE!")
                else:
                    print(f"Round {round_num}: Connection lost")
                    break
            
            # Update server statistics
            with self.stats_lock:
                self.total_games += num_rounds
                self.total_wins += client_losses  # Server wins when client loses
                self.total_losses += client_wins
                self.total_ties += client_ties
            
            print(f"\n[{client_address}] {client_name} finished: {client_wins}W-{client_losses}L-{client_ties}T")
            print(f"Server stats: {self.total_wins}W-{self.total_losses}L-{self.total_ties}T ({self.total_games} total games)")
        
        except socket.timeout:
            print(f"[{client_address}] Connection timeout")
        except Exception as e:
            print(f"[{client_address}] Error: {e}")
        finally:
            client_socket.close()
    
    def _play_round(self, client_socket: socket.socket, client_name: str) -> int:
        """
        Play a single round of blackjack with a client.
        
        Args:
            client_socket: Connected client socket
            client_name: Name of the client
            
        Returns:
            Result code (RESULT_WIN, RESULT_LOSS, RESULT_TIE, or -1 on error)
        """
        game = BlackjackGame()
        
        try:
            # Deal initial cards
            player_card1, player_card2, dealer_card = game.deal_initial_cards()
            
            print(f"Player cards: {player_card1}, {player_card2} (Total: {game.player_total})")
            print(f"Dealer shows: {dealer_card} (Hidden card: {game.dealer_hand[1]})")
            
            # Send player's two cards
            client_socket.sendall(create_payload_message(RESULT_NOT_OVER, player_card1))
            client_socket.sendall(create_payload_message(RESULT_NOT_OVER, player_card2))
            
            # Send dealer's first (visible) card
            client_socket.sendall(create_payload_message(RESULT_NOT_OVER, dealer_card))
            
            # Player's turn
            player_bust = False
            while not player_bust:
                # Receive player decision (exactly 10 bytes)
                decision_data = recv_exact(client_socket, 10)
                if len(decision_data) < 10:
                    print(f"Connection closed while waiting for decision")
                    return -1
                decision = parse_payload_message(decision_data)
                
                if not decision:
                    print("Invalid decision message")
                    return -1
                
                print(f"{client_name} chose: {decision}")
                
                if decision == "Stand":
                    break
                elif decision == "Hitt":
                    new_card, new_total, is_bust = game.player_hit()
                    print(f"Player drew: {new_card} (Total: {new_total})")
                    
                    if is_bust:
                        print(f"Player BUSTS with {new_total}!")
                        client_socket.sendall(create_payload_message(RESULT_LOSS, new_card))
                        return RESULT_LOSS
                    else:
                        client_socket.sendall(create_payload_message(RESULT_NOT_OVER, new_card))
            
            # Dealer's turn
            print(f"\nDealer reveals hidden card: {game.dealer_hand[1]} (Total: {game.dealer_total})")
            client_socket.sendall(create_payload_message(RESULT_NOT_OVER, game.dealer_hand[1]))
            
            drawn_cards = game.dealer_play()
            for card in drawn_cards:
                print(f"Dealer draws: {card} (Total: {game.dealer_total})")
                client_socket.sendall(create_payload_message(RESULT_NOT_OVER, card))
                time.sleep(0.1)  # Small delay for readability
            
            if game.dealer_total > BUST_THRESHOLD:
                print(f"Dealer BUSTS with {game.dealer_total}!")
            else:
                print(f"Dealer stands with {game.dealer_total}")
            
            # Determine winner
            result = game.determine_winner()
            print(f"Final: Player {game.player_total} vs Dealer {game.dealer_total}")
            
            # Send final result
            client_socket.sendall(create_payload_message(result, None))
            
            return result
        
        except Exception as e:
            print(f"Error during round: {e}")
            return -1
    
    def stop(self):
        """Stop the server and clean up resources."""
        self.running = False
        if self.tcp_socket:
            self.tcp_socket.close()
        if self.udp_socket:
            self.udp_socket.close()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the server application."""
    server = BlackjackServer(SERVER_NAME)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        server.stop()
        print("Server stopped.")


if __name__ == "__main__":
    main()

