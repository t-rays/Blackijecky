# Source Code Directory

## Overview

This directory contains all the core Python source code for the Blackjack client-server application. The implementation follows the protocol specification for the Intro to Computer Networks 2025 Hackathon.

## Files

### `blackjack_server.py`
**Purpose**: Main game server implementation

**Functionality**:
- Broadcasts UDP offer messages on port 13122
- Accepts TCP connections from clients
- Manages multiple concurrent game sessions using threads
- Implements complete Blackjack game logic (dealer rules: hit until 17+)
- Handles all protocol message types (offer, request, payload)
- Tracks game statistics

**Usage**:
```bash
python3 src/blackjack_server.py
```

**Configuration**:
- `SERVER_NAME`: Team name (line 48) - change to your team name
- `TCP_PORT`: Dynamically assigned (binds to port 0)

### `blackjack_client.py`
**Purpose**: Terminal-based game client

**Functionality**:
- Listens for UDP offer broadcasts on port 13122
- Connects to discovered servers via TCP
- Implements simple playing strategy (stand on 17+)
- Tracks session and overall statistics
- Provides user-friendly console interface

**Usage**:
```bash
python3 src/blackjack_client.py
```

**Configuration**:
- `CLIENT_NAME`: Team name (line 46) - change to your team name

### `tcp_utils.py`
**Purpose**: TCP utility functions

**Functionality**:
- `recv_exact()`: Receives exactly N bytes from a socket
- Handles partial receives correctly
- Returns empty bytes if connection closes

**Usage**: Imported by server and client for reliable message reception

### `web_bridge.py`
**Purpose**: Web interface bridge server (optional bonus feature)

**Functionality**:
- HTTP server on port 8080
- Bridges web client to TCP blackjack server
- Implements Server-Sent Events (SSE) for real-time updates
- Manages game sessions between web interface and TCP server
- Serves static web files (HTML, CSS, JS)

**Usage**:
```bash
# Start the blackjack server first
python3 src/blackjack_server.py

# Then start the web bridge (in another terminal)
python3 src/web_bridge.py

# Open http://localhost:8080 in your browser
```

## Instructions

### Running the Server
1. Update `SERVER_NAME` in `blackjack_server.py` (line 48)
2. Run: `python3 src/blackjack_server.py`
3. Server will print its IP address and TCP port
4. Server automatically broadcasts offers every second

### Running the Client
1. Update `CLIENT_NAME` in `blackjack_client.py` (line 46)
2. Run: `python3 src/blackjack_client.py`
3. Enter number of rounds to play
4. Client will discover server and connect automatically

### Running the Web Interface
1. Start the blackjack server: `python3 src/blackjack_server.py`
2. Start the web bridge: `python3 src/web_bridge.py`
3. Open `http://localhost:8080` in your browser
4. Enter your name and number of rounds
5. Click "Discover Server" to start playing

## Protocol Compliance

All files implement the required protocol:
- **Magic Cookie**: 0xabcddcba
- **UDP Port**: 13122 (hardcoded for client)
- **Message Types**: Offer (0x2), Request (0x3), Payload (0x4)
- **Card Encoding**: Rank (2 ASCII bytes "01"-"13") + Suit (1 byte 0-3)
- **Decision Format**: "Hitt" or "Stand" (5 bytes)

## Dependencies

All files use only Python standard library:
- `socket` - Network communication
- `struct` - Binary message packing/unpacking
- `threading` - Concurrent client handling
- `time` - Delays and timeouts
- `random` - Card shuffling
- `http.server` - Web bridge (web_bridge.py only)
- `json` - Web API (web_bridge.py only)
- `queue` - Event queue (web_bridge.py only)

No external dependencies required!

