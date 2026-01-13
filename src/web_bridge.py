#!/usr/bin/env python3
"""
Web Bridge Server for Blackjack Web Interface
Acts as a bridge between the web client and the TCP blackjack server.
"""

import socket
import struct
import threading
import time
import json
import queue
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blackjack_client as client_module
import blackjack_server as server_module
from tcp_utils import recv_exact


# ============================================================================
# CONSTANTS
# ============================================================================

UDP_PORT = 13122
DISCOVERY_TIMEOUT = 5
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4

RESULT_NOT_OVER = 0x0
RESULT_TIE = 0x1
RESULT_LOSS = 0x2
RESULT_WIN = 0x3

SUITS = ['♥', '♦', '♣', '♠']
RANK_NAMES = ['', 'A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

BUST_THRESHOLD = 21


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_hand_value_from_dicts(hand: list) -> int:
    """
    Calculate the total value of a hand from card dictionaries.
    For simplicity, Aces are valued as 1 (as allowed by forum Q&A).
    
    Args:
        hand: List of card dictionaries with 'rank' and 'value' keys
        
    Returns:
        Total value of the hand
    """
    # For simplicity, just sum the values (Ace value is already set to 1 in card.get_value())
    return sum(card.get('value', 0) for card in hand)


# ============================================================================
# GAME SESSION MANAGER
# ============================================================================

class GameSession:
    """Manages a single game session between web client and TCP server."""
    
    def __init__(self, session_id: str, server_ip: str, tcp_port: int, num_rounds: int, client_name: str):
        self.session_id = session_id
        self.server_ip = server_ip
        self.tcp_port = tcp_port
        self.num_rounds = num_rounds
        self.client_name = client_name
        self.tcp_socket = None
        self.current_round = 1  # Start at round 1
        self.player_hand = []
        self.dealer_hand = []
        self.player_total = 0
        self.dealer_total = 0
        self.game_state = "disconnected"  # disconnected, connecting, playing, waiting_decision, dealer_turn, finished
        self.last_result = None
        self.session_wins = 0
        self.session_losses = 0
        self.session_ties = 0
        self.round_result = None
        self.error_message = None
        
        # SSE support: event queue and receiver thread
        self.event_queue = queue.Queue()
        self.receiver_thread = None
        self.receiving = False
        self.lock = threading.Lock()
    
    def connect(self) -> bool:
        """Connect to the TCP server and start background receiver."""
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.settimeout(120)  # Increased timeout to 120 seconds for longer games
            self.tcp_socket.connect((self.server_ip, self.tcp_port))
            
            # Send request message
            request_msg = client_module.create_request_message(self.num_rounds, self.client_name)
            self.tcp_socket.sendall(request_msg)
            
            self.game_state = "playing"
            self.receiving = True
            
            # Start background thread to receive cards
            self.receiver_thread = threading.Thread(target=self._tcp_receiver, daemon=True)
            self.receiver_thread.start()
            
            return True
        except Exception as e:
            self.error_message = str(e)
            self.game_state = "error"
            return False
    
    def _tcp_receiver(self):
        """Background thread that receives cards from TCP and pushes to event queue."""
        while self.receiving and self.tcp_socket:
            try:
                # Receive exactly 9 bytes (server payload message size)
                data = recv_exact(self.tcp_socket, 9)
                if len(data) < 9:
                    # Connection closed
                    with self.lock:
                        current_round = self.current_round
                        total_rounds = self.num_rounds
                        game_state = self.game_state
                    print(f"[TCP] Connection closed, received {len(data)} bytes (round {current_round}/{total_rounds}, state={game_state})")
                    # Check if this is expected (all rounds complete and game finished)
                    # But also check if we just finished the last round
                    is_expected_close = (current_round >= total_rounds and game_state == 'finished')
                    if not is_expected_close:
                        # Unexpected closure - send error
                        print(f"[TCP] Unexpected connection close during round {current_round}/{total_rounds}")
                        self.event_queue.put({'error': 'Connection closed', 'state': self.get_state()})
                    else:
                        print(f"[TCP] Connection closed after all rounds complete - expected")
                    break
                
                # Parse the message
                parsed = client_module.parse_payload_message(data)
                if not parsed:
                    print(f"[TCP] Invalid message: {data.hex()}")
                    continue
                
                result, card = parsed
                
                # Process this message
                card_info = None
                if card:
                    card_info = {
                        'rank': card.rank,
                        'suit': card.suit,
                        'rank_name': RANK_NAMES[card.rank],
                        'suit_symbol': SUITS[card.suit],
                        'value': card.get_value(),
                        'display': f"{RANK_NAMES[card.rank]}{SUITS[card.suit]}"
                    }
                
                # Update state
                with self.lock:
                    # Check if we're starting a new round (finished state + new cards arriving)
                    if self.game_state == "finished" and card_info and result == RESULT_NOT_OVER:
                        # New round starting - increment round and reset hands
                        if self.current_round < self.num_rounds:
                            self.current_round += 1
                        print(f"[ROUND] Starting new round {self.current_round}, resetting hands (was finished, now receiving cards)")
                        self.player_hand = []
                        self.dealer_hand = []
                        self.player_total = 0
                        self.dealer_total = 0
                        self.round_result = None
                        self.game_state = "playing"
                    
                    # Determine if this is a final result card (random card sent with final result)
                    # vs a bust card (RESULT_LOSS during player's turn)
                    # Final results after dealer's turn have random cards that shouldn't be added
                    # But bust cards during player's turn should be added
                    is_final_result_card = (
                        result in [RESULT_WIN, RESULT_LOSS, RESULT_TIE] and 
                        self.game_state in ["dealer_turn", "finished"]
                    )
                    
                    # Only add cards to hands if it's NOT a final result card
                    # Final results after dealer plays include a random card for message structure
                    # But bust cards during player's turn are real game cards that should be added
                    if card_info and not is_final_result_card:
                        # Determine which hand gets the card based on hand sizes and game state
                        # Initial deal: 2 player cards, then 1 dealer card
                        player_count = len(self.player_hand)
                        dealer_count = len(self.dealer_hand)
                        
                        if player_count < 2:
                            # First 2 cards go to player
                            self.player_hand.append(card_info)
                        elif dealer_count == 0:
                            # Third card goes to dealer (visible card)
                            self.dealer_hand.append(card_info)
                        elif self.game_state == "waiting_decision":
                            # Player's turn: card goes to player (hit)
                            self.player_hand.append(card_info)
                        elif self.game_state == "dealer_turn":
                            # Dealer's turn: card goes to dealer
                            self.dealer_hand.append(card_info)
                        elif player_count >= 2 and dealer_count >= 1:
                            # After initial deal, if we have 2+ player and 1+ dealer cards,
                            # and we're not in waiting_decision, it's dealer's turn
                            self.dealer_hand.append(card_info)
                        else:
                            # Fallback: default to dealer if dealer already has cards
                            if dealer_count > 0:
                                self.dealer_hand.append(card_info)
                            else:
                                # Shouldn't happen, but default to player
                                self.player_hand.append(card_info)
                        
                        # Recalculate totals (with flexible Ace handling)
                        self.player_total = calculate_hand_value_from_dicts(self.player_hand)
                        self.dealer_total = calculate_hand_value_from_dicts(self.dealer_hand)
                    
                    # Update game state based on result and hand sizes
                    if result == RESULT_LOSS:
                        self.game_state = "finished"
                        self.round_result = "LOSS"
                        self.session_losses += 1
                        print(f"[ROUND] Round {self.current_round} finished: LOSS")
                    elif result == RESULT_WIN:
                        self.game_state = "finished"
                        self.round_result = "WIN"
                        self.session_wins += 1
                        print(f"[ROUND] Round {self.current_round} finished: WIN")
                    elif result == RESULT_TIE:
                        self.game_state = "finished"
                        self.round_result = "TIE"
                        self.session_ties += 1
                        print(f"[ROUND] Round {self.current_round} finished: TIE")
                    elif result == RESULT_NOT_OVER:
                        # Check hand sizes AFTER adding card
                        player_count = len(self.player_hand)
                        dealer_count = len(self.dealer_hand)
                        
                        if player_count == 2 and dealer_count == 1:
                            # Initial deal complete - wait for player decision
                            self.game_state = "waiting_decision"
                        elif self.game_state == "waiting_decision":
                            # Player hit - check if bust
                            if self.player_total > 21:
                                self.game_state = "finished"
                                self.round_result = "LOSS"
                                self.session_losses += 1
                            else:
                                # Player can still hit or stand
                                self.game_state = "waiting_decision"
                        elif dealer_count > 1:
                            # Dealer's turn (has more than just the visible card)
                            self.game_state = "dealer_turn"
                        elif player_count < 2 or dealer_count < 1:
                            # Still receiving initial cards
                            self.game_state = "playing"
                        else:
                            # If we have 2 player and dealer has cards, and not waiting_decision, it's dealer turn
                            if player_count >= 2 and dealer_count >= 1 and self.game_state != "waiting_decision":
                                self.game_state = "dealer_turn"
                            else:
                                self.game_state = "playing"
                        
                # Log after all updates (capture state outside lock to ensure we have the final state)
                with self.lock:
                    final_state = self.game_state
                    final_player_count = len(self.player_hand)
                    final_dealer_count = len(self.dealer_hand)
                
                print(f"[TCP] Received: result={result}, card={card_info['display'] if card_info else None}, player={final_player_count}, dealer={final_dealer_count}, state={final_state}")
                
                # Push to event queue for SSE
                # Get current state (after all updates) for the event
                current_state = self.get_state()
                event_data = {
                    'result': result,
                    'card': card_info,
                    'result_name': ['NOT_OVER', 'TIE', 'LOSS', 'WIN'][result] if result < 4 else 'UNKNOWN',
                    'state': current_state
                }
                
                # Queue final result messages
                # For bust cards (result with card), always send
                # For final result with no card, always send (it's the round end notification)
                # The state is "finished" at this point, so the client will get the notification
                if result in [RESULT_WIN, RESULT_LOSS, RESULT_TIE]:
                    if card_info:
                        # Bust card - always send (this is the card that caused the loss)
                        self.event_queue.put(event_data)
                    else:
                        # Final result with no card - always send if we detected it as final result
                        # (we checked is_final_result before any new round processing)
                        if is_final_result:
                            self.event_queue.put(event_data)
                            print(f"[TCP] Queued final result event (no card) - round finished")
                        else:
                            # This shouldn't happen, but skip if somehow state changed
                            print(f"[TCP] Skipping final result event - state changed")
                else:
                    # Normal card or NOT_OVER - always send
                    self.event_queue.put(event_data)
                
            except socket.timeout:
                continue
            except socket.error as e:
                # Socket error - connection might be closed
                error_msg = f"Socket error: {e}"
                print(f"[TCP] {error_msg}")
                self.error_message = error_msg
                with self.lock:
                    current_state = self.get_state()
                self.event_queue.put({'error': error_msg, 'state': current_state})
                break
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                print(f"[TCP] {error_msg}")
                self.error_message = error_msg
                with self.lock:
                    current_state = self.get_state()
                self.event_queue.put({'error': error_msg, 'state': current_state})
                break
    
    def receive_card(self) -> dict:
        """Receive a card from the event queue (non-blocking, for polling fallback)."""
        try:
            return self.event_queue.get(timeout=0.1)
        except queue.Empty:
            return None
    
    def send_decision(self, decision: str) -> bool:
        """Send hit/stand decision to server."""
        try:
            if decision not in ["Hitt", "Stand"]:
                print(f"[DECISION] Invalid decision: {decision}")
                return False
            
            if not self.tcp_socket:
                print(f"[DECISION] TCP socket is None")
                self.error_message = "TCP socket not connected"
                return False
            
            print(f"[DECISION] Sending decision to server: {decision}")
            message = client_module.create_payload_message(decision)
            print(f"[DECISION] Message bytes: {message.hex()}")
            self.tcp_socket.sendall(message)
            print(f"[DECISION] Decision sent successfully: {decision}")
            
            # Update state: if Stand, next cards are dealer's
            with self.lock:
                if decision == "Stand":
                    self.game_state = "dealer_turn"
                    print(f"[DECISION] State changed to dealer_turn after Stand")
            
            return True
        except socket.error as e:
            self.error_message = f"Socket error: {e}"
            print(f"[DECISION] Socket error sending decision: {e}")
            return False
        except Exception as e:
            self.error_message = str(e)
            print(f"[DECISION] Error sending decision: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_state(self) -> dict:
        """Get current game state as dictionary."""
        return {
            'session_id': self.session_id,
            'game_state': self.game_state,
            'current_round': self.current_round,
            'num_rounds': self.num_rounds,
            'player_hand': self.player_hand,
            'dealer_hand': self.dealer_hand,
            'player_total': self.player_total,
            'dealer_total': self.dealer_total,
            'round_result': self.round_result,
            'session_wins': self.session_wins,
            'session_losses': self.session_losses,
            'session_ties': self.session_ties,
            'error_message': self.error_message
        }
    
    def close(self):
        """Close the TCP connection and stop receiver."""
        self.receiving = False
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
        if self.receiver_thread:
            self.receiver_thread.join(timeout=1)


# ============================================================================
# SESSION MANAGER
# ============================================================================

class SessionManager:
    """Manages all active game sessions."""
    
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
    
    def create_session(self, server_ip: str, tcp_port: int, num_rounds: int, client_name: str) -> str:
        """Create a new game session."""
        session_id = f"session_{int(time.time() * 1000)}"
        session = GameSession(session_id, server_ip, tcp_port, num_rounds, client_name)
        
        with self.lock:
            self.sessions[session_id] = session
        
        return session_id
    
    def get_session(self, session_id: str) -> GameSession:
        """Get a session by ID."""
        with self.lock:
            return self.sessions.get(session_id)
    
    def remove_session(self, session_id: str):
        """Remove a session."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].close()
                del self.sessions[session_id]


# Global session manager
session_manager = SessionManager()


# ============================================================================
# HTTP REQUEST HANDLER
# ============================================================================

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server to handle concurrent requests."""
    daemon_threads = True


class WebBridgeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for web bridge."""
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Serve static files
        if path == '/' or path == '/index.html':
            self.serve_file('web_interface.html', 'text/html')
        elif path == '/style.css':
            self.serve_file('web_style.css', 'text/css')
        elif path == '/script.js':
            self.serve_file('web_script.js', 'text/javascript')
        
        # API endpoints
        elif path == '/api/discover':
            self.handle_discover()
        elif path == '/api/session/create':
            self.handle_create_session()
        elif path == '/api/session/state':
            self.handle_get_state()
        elif path == '/api/session/decision':
            self.handle_send_decision()
        elif path == '/api/session/receive':
            self.handle_receive_card()
        elif path == '/api/session/events':
            self.handle_sse_stream()
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        print(f"[HTTP] POST request: {path}")
        
        if path == '/api/session/create':
            self.handle_create_session()
        elif path == '/api/session/decision':
            self.handle_send_decision()
        else:
            print(f"[HTTP] POST to unknown path: {path}")
            self.send_error(404)
    
    def serve_file(self, filename: str, content_type: str):
        """Serve a static file from the web directory."""
        try:
            # Get the directory where this script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Web files are in ../web/ relative to src/
            web_dir = os.path.join(script_dir, '..', 'web')
            filepath = os.path.join(web_dir, filename)
            
            with open(filepath, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)
    
    def handle_discover(self):
        """Handle server discovery request."""
        try:
            # Discover server using UDP
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            udp_socket.bind(('', UDP_PORT))
            udp_socket.settimeout(DISCOVERY_TIMEOUT)
            
            try:
                data, address = udp_socket.recvfrom(1024)
                server_ip = address[0]
                
                parsed = client_module.parse_offer_message(data)
                if parsed:
                    tcp_port, server_name = parsed
                    response = {
                        'success': True,
                        'server_ip': server_ip,
                        'tcp_port': tcp_port,
                        'server_name': server_name
                    }
                else:
                    response = {'success': False, 'error': 'Invalid offer message'}
            except socket.timeout:
                response = {'success': False, 'error': 'No server found'}
            finally:
                udp_socket.close()
        except Exception as e:
            response = {'success': False, 'error': str(e)}
        
        self.send_json_response(response)
    
    def handle_create_session(self):
        """Handle session creation request."""
        try:
            if self.command == 'POST':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
            else:
                # GET request with query parameters
                query_params = parse_qs(urlparse(self.path).query)
                data = {k: v[0] if v else '' for k, v in query_params.items()}
            
            server_ip = data.get('server_ip')
            tcp_port = int(data.get('tcp_port', 0))
            num_rounds = int(data.get('num_rounds', 1))
            client_name = data.get('client_name', 'WebPlayer')
            
            print(f"[SESSION] Creating session: {client_name} -> {server_ip}:{tcp_port} ({num_rounds} rounds)")
            
            session_id = session_manager.create_session(server_ip, tcp_port, num_rounds, client_name)
            session = session_manager.get_session(session_id)
            
            if session.connect():
                print(f"[SESSION] Session {session_id} connected successfully")
                response = {'success': True, 'session_id': session_id}
            else:
                print(f"[SESSION] Session {session_id} connection failed: {session.error_message}")
                response = {'success': False, 'error': session.error_message}
        except Exception as e:
            print(f"[SESSION] Error creating session: {e}")
            import traceback
            traceback.print_exc()
            response = {'success': False, 'error': str(e)}
        
        self.send_json_response(response)
    
    def handle_get_state(self):
        """Handle get state request."""
        query_params = parse_qs(urlparse(self.path).query)
        session_id = query_params.get('session_id', [None])[0]
        
        if not session_id:
            self.send_json_response({'success': False, 'error': 'No session_id provided'})
            return
        
        session = session_manager.get_session(session_id)
        if not session:
            self.send_json_response({'success': False, 'error': 'Session not found'})
            return
        
        response = {'success': True, 'state': session.get_state()}
        self.send_json_response(response)
    
    def handle_send_decision(self):
        """Handle send decision request."""
        print(f"[HTTP] handle_send_decision called, method={self.command}")
        try:
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                print(f"[HTTP] Reading {content_length} bytes from request body...")
                post_data = self.rfile.read(content_length)
                print(f"[HTTP] Read {len(post_data)} bytes")
                data = json.loads(post_data.decode('utf-8'))
                print(f"[HTTP] Parsed JSON: {data}")
            else:
                query_params = parse_qs(urlparse(self.path).query)
                data = {k: v[0] if v else '' for k, v in query_params.items()}
            
            session_id = data.get('session_id')
            decision = data.get('decision')
            
            print(f"[HTTP] Decision request: session={session_id}, decision={decision}")
            
            session = session_manager.get_session(session_id)
            if not session:
                print(f"[HTTP] Session not found: {session_id}")
                response = {'success': False, 'error': 'Session not found'}
            elif session.send_decision(decision):
                print(f"[HTTP] Decision sent successfully")
                response = {'success': True}
            else:
                error_msg = session.error_message or 'Invalid decision or connection error'
                print(f"[HTTP] Decision failed: {error_msg}")
                response = {'success': False, 'error': error_msg}
        except KeyError as e:
            print(f"[HTTP] Missing header: {e}")
            response = {'success': False, 'error': f'Missing header: {e}'}
        except Exception as e:
            print(f"[HTTP] Error handling decision: {e}")
            import traceback
            traceback.print_exc()
            response = {'success': False, 'error': str(e)}
        
        print(f"[HTTP] Sending response: {response}")
        self.send_json_response(response)
        print(f"[HTTP] Response sent")
    
    def handle_receive_card(self):
        """Handle receive card request (polling fallback)."""
        query_params = parse_qs(urlparse(self.path).query)
        session_id = query_params.get('session_id', [None])[0]
        
        if not session_id:
            self.send_json_response({'success': False, 'error': 'No session_id provided'})
            return
        
        session = session_manager.get_session(session_id)
        if not session:
            self.send_json_response({'success': False, 'error': 'Session not found'})
            return
        
        card_data = session.receive_card()  # Non-blocking from queue
        if card_data:
            response = {'success': True, 'card_data': card_data, 'state': session.get_state()}
        else:
            response = {'success': True, 'card_data': None, 'state': session.get_state()}
        
        self.send_json_response(response)
    
    def handle_sse_stream(self):
        """Handle Server-Sent Events stream for real-time updates."""
        query_params = parse_qs(urlparse(self.path).query)
        session_id = query_params.get('session_id', [None])[0]
        
        if not session_id:
            print("[SSE] No session_id provided")
            self.send_error(400, "No session_id provided")
            return
        
        session = session_manager.get_session(session_id)
        if not session:
            print(f"[SSE] Session not found: {session_id}")
            self.send_error(404, "Session not found")
            return
        
        print(f"[SSE] Starting stream for session: {session_id}")
        
        # Set up SSE headers
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Send initial state immediately
        try:
            initial_state = {
                'result': RESULT_NOT_OVER,
                'card': None,
                'result_name': 'NOT_OVER',
                'state': session.get_state()
            }
            json_data = json.dumps(initial_state)
            self.wfile.write(f"data: {json_data}\n\n".encode('utf-8'))
            self.wfile.flush()
            state = session.get_state()
            print(f"[SSE] Sent initial state: game_state={state['game_state']}, player={len(state['player_hand'])}, dealer={len(state['dealer_hand'])}, queue_size={session.event_queue.qsize()}")
        except Exception as e:
            print(f"[SSE] Error sending initial state: {e}")
        
        # Stream events as they arrive
        try:
            while session.receiving:
                try:
                    event_data = session.event_queue.get(timeout=1)
                    # Format as SSE
                    json_data = json.dumps(event_data)
                    print(f"[SSE] Sending event: state={event_data.get('state', {}).get('game_state')}, card={event_data.get('card', {}).get('display') if event_data.get('card') else None}")
                    self.wfile.write(f"data: {json_data}\n\n".encode('utf-8'))
                    self.wfile.flush()
                    
                    # Don't break on finished - continue for multiple rounds
                    # The session will close when all rounds are complete or connection closes
                except queue.Empty:
                    # Send keepalive
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected
            pass
        except Exception as e:
            # Send error event
            error_data = json.dumps({'error': str(e)})
            try:
                self.wfile.write(f"data: {error_data}\n\n".encode('utf-8'))
                self.wfile.flush()
            except:
                pass
    
    def send_json_response(self, data: dict):
        """Send JSON response."""
        json_data = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(json_data)))
        self.end_headers()
        self.wfile.write(json_data)
    
    def log_message(self, format, *args):
        """Log HTTP requests for debugging."""
        # Log API calls and errors, but skip static file requests
        message = format % args
        if '/api/' in message or '404' in message or '500' in message:
            print(f"[HTTP] {message}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Start the web bridge server."""
    port = 8080
    server = ThreadingHTTPServer(('', port), WebBridgeHandler)
    
    print("="*60)
    print("Blackjack Web Bridge Server")
    print("="*60)
    print(f"Web interface available at: http://localhost:{port}")
    print(f"Make sure the blackjack server is running!")
    print("="*60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web bridge server...")
        server.shutdown()


if __name__ == "__main__":
    main()

