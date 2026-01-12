# Blackjack Client-Server Application

**Intro to Computer Networks 2025 Hackathon**

A complete implementation of a networked Blackjack game with UDP server discovery and TCP game sessions.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Protocol Specification](#protocol-specification)
- [Code Structure](#code-structure)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This project implements a distributed Blackjack game system where:
- **Servers** host games and broadcast their availability via UDP
- **Clients** discover servers automatically and connect to play multiple rounds
- All communication follows a strict binary protocol specification
- Full compatibility between any team's client and server implementations

## ✨ Features

### Server Features
- ✅ UDP broadcast for automatic server discovery
- ✅ Concurrent handling of multiple clients using threads
- ✅ Complete Blackjack game logic with proper dealer rules
- ✅ Comprehensive error handling and timeout management
- ✅ Real-time game statistics tracking
- ✅ Detailed logging of all game events

### Client Features
- ✅ Automatic server discovery via UDP listening
- ✅ Simple but effective playing strategy (stand on 17+)
- ✅ Session statistics and win rate calculation
- ✅ User-friendly console interface
- ✅ Automatic reconnection after each game session
- ✅ Graceful error handling and recovery

### Web Interface Features (NEW!)
- ✅ Beautiful modern web-based UI
- ✅ Visual card display with animations
- ✅ Real-time game state updates
- ✅ Interactive hit/stand controls
- ✅ Live statistics tracking
- ✅ Responsive design (works on mobile)
- ✅ No external dependencies required

## 🏗️ Architecture

### Network Protocol

The application uses a hybrid UDP/TCP protocol:

1. **Discovery Phase (UDP)**
   - Server broadcasts "offer" messages to UDP port 13122
   - Clients listen on port 13122 for offers
   - Offers contain server name and TCP port

2. **Game Phase (TCP)**
   - Client connects to server's advertised TCP port
   - Request/response pattern for game actions
   - Binary protocol with magic cookie validation

### Message Types

| Type | Direction | Protocol | Purpose |
|------|-----------|----------|---------|
| Offer | Server → Client | UDP | Announce server availability |
| Request | Client → Server | TCP | Request game session |
| Payload | Bidirectional | TCP | Game actions and cards |

## 📦 Installation

### Prerequisites

- Python 3.7 or higher
- No external dependencies required (uses only standard library)

### Project Structure

```
Blackijecky/
├── README.md                 # This file
├── requirements.txt          # Python dependencies (none required)
├── .gitignore               # Git ignore file
├── src/                     # Core source files
│   ├── blackjack_server.py  # Game server
│   ├── blackjack_client.py  # Terminal client
│   ├── web_bridge.py        # Web interface bridge
│   └── tcp_utils.py         # TCP utilities
├── web/                     # Web interface files
│   ├── web_interface.html   # Main HTML page
│   ├── web_script.js        # Client-side JavaScript
│   └── web_style.css        # Stylesheet
├── tests/                   # Test files
│   ├── test_blackjack.py    # Unit tests
│   ├── test_integration.py  # Integration tests
│   └── test_web_*.py        # Web interface tests
└── docs/                    # Documentation
    ├── TESTING.md           # Testing guide
    ├── WEB_INTERFACE.md     # Web interface docs
    └── ...                  # Additional documentation
```

### Setup

1. **Navigate to the project directory:**
   ```bash
   cd Blackijecky
   ```

2. **Configure team names:**
   
   Edit `src/blackjack_server.py`:
   ```python
   SERVER_NAME = "YourTeamName"  # Line 41
   ```
   
   Edit `src/blackjack_client.py`:
   ```python
   CLIENT_NAME = "YourTeamName"  # Line 35
   ```

3. **Make files executable (optional):**
   ```bash
   chmod +x src/blackjack_server.py
   chmod +x src/blackjack_client.py
   chmod +x src/web_bridge.py
   ```

## 🚀 Usage

### Starting the Server

```bash
python3 src/blackjack_server.py
```

**Expected output:**
```
Server started, listening on IP address 192.168.1.100
TCP port: 54321
Server name: YourTeamName
============================================================
Waiting for clients to connect...
```

The server will:
- Bind to a random available TCP port
- Start broadcasting UDP offers every second
- Accept and handle multiple client connections concurrently

### Starting the Client (Terminal)

```bash
python3 src/blackjack_client.py
```

**Expected output:**
```
============================================================
Blackjack Client - YourTeamName
============================================================

How many rounds would you like to play? (0 to exit): 3

Client started, listening for offer requests...
Received offer from DealerNadav at 192.168.1.100
Connected to server at 192.168.1.100:54321

============================================================
Round 1/3
============================================================
Your card: A♥
Your card: 7♦
Your total: 18
Dealer's visible card: K♣
...
```

### Starting the Web Interface (NEW!)

1. **Start the server** (if not already running):
   ```bash
   python3 src/blackjack_server.py
   ```

2. **Start the web bridge** (in a new terminal):
   ```bash
   python3 src/web_bridge.py
   ```

3. **Open in browser**:
   ```
   http://localhost:8080
   ```

4. **Play**:
   - Enter your name and number of rounds
   - Click "Discover Server"
   - Enjoy the visual game experience!

See [WEB_INTERFACE.md](WEB_INTERFACE.md) for detailed web interface documentation.

### Workflow

1. **Client requests rounds**: User enters number of rounds (1-255)
2. **Server discovery**: Client listens for UDP broadcasts
3. **Connection**: Client connects to first available server
4. **Game session**: Plays all requested rounds
5. **Statistics**: Displays session and overall statistics
6. **Repeat**: Returns to step 1 for next session

## 📡 Protocol Specification

### Offer Message (UDP, Server → Client)

| Field | Size | Type | Description |
|-------|------|------|-------------|
| Magic Cookie | 4 bytes | uint32 | 0xabcddcba |
| Message Type | 1 byte | uint8 | 0x02 |
| TCP Port | 2 bytes | uint16 | Server's TCP port |
| Server Name | 32 bytes | string | Null-padded/truncated |

**Total: 39 bytes**

### Request Message (TCP, Client → Server)

| Field | Size | Type | Description |
|-------|------|------|-------------|
| Magic Cookie | 4 bytes | uint32 | 0xabcddcba |
| Message Type | 1 byte | uint8 | 0x03 |
| Num Rounds | 1 byte | uint8 | 1-255 rounds |
| Client Name | 32 bytes | string | Null-padded/truncated |

**Total: 38 bytes**

### Payload Message (TCP, Bidirectional)

**Client to Server:**
| Field | Size | Type | Description |
|-------|------|------|-------------|
| Magic Cookie | 4 bytes | uint32 | 0xabcddcba |
| Message Type | 1 byte | uint8 | 0x04 |
| Decision | 5 bytes | string | "Hittt" or "Stand" |

**Total: 10 bytes**

**Server to Client:**
| Field | Size | Type | Description |
|-------|------|------|-------------|
| Magic Cookie | 4 bytes | uint32 | 0xabcddcba |
| Message Type | 1 byte | uint8 | 0x04 |
| Result | 1 byte | uint8 | 0=continue, 1=tie, 2=loss, 3=win |
| Card | 3 bytes | encoded | Rank (2 bytes) + Suit (1 byte) |

**Total: 9 bytes**

### Card Encoding

- **Rank**: 2 ASCII bytes ("01"-"13")
  - 01 = Ace, 02-10 = Number cards, 11 = Jack, 12 = Queen, 13 = King
- **Suit**: 1 byte (0-3)
  - 0 = Heart (♥), 1 = Diamond (♦), 2 = Club (♣), 3 = Spade (♠)

**Example:** King of Hearts = `b'130'` (bytes: 0x31, 0x33, 0x00)

## 📁 Code Structure

### Server Architecture

```
src/blackjack_server.py
├── Constants (Lines 18-47)
├── Card & Deck Classes (Lines 52-128)
│   ├── Card: Represents individual cards
│   └── Deck: 52-card deck with shuffling
├── BlackjackGame Class (Lines 133-234)
│   ├── deal_initial_cards()
│   ├── player_hit()
│   ├── dealer_play()
│   └── determine_winner()
├── Message Handling (Lines 239-322)
│   ├── create_offer_message()
│   ├── parse_request_message()
│   ├── create_payload_message()
│   └── parse_payload_message()
└── BlackjackServer Class (Lines 327-529)
    ├── start(): Initialize sockets
    ├── _broadcast_offers(): UDP thread
    ├── _accept_clients(): Main accept loop
    ├── _handle_client(): Client session handler
    └── _play_round(): Single round logic
```

### Client Architecture

```
src/blackjack_client.py
├── Constants (Lines 18-35)
├── Card Class (Lines 40-92)
│   ├── get_value()
│   └── decode(): Parse from bytes
├── Message Handling (Lines 97-203)
│   ├── parse_offer_message()
│   ├── create_request_message()
│   ├── create_payload_message()
│   └── parse_payload_message()
└── BlackjackClient Class (Lines 208-481)
    ├── discover_server(): UDP listening
    ├── play_session(): Full game session
    ├── _play_round(): Single round logic
    ├── _make_decision(): Strategy logic
    └── run_forever(): Main loop
```

## 🧪 Testing

### Testing Checklist

- [ ] Server starts and displays correct IP/port
- [ ] Server broadcasts UDP offers every second
- [ ] Client receives and parses offer messages
- [ ] Client connects via TCP successfully
- [ ] Game plays through all rounds correctly
- [ ] Win/loss/tie conditions work properly
- [ ] Statistics are calculated correctly
- [ ] Client reconnects after session ends
- [ ] Multiple clients can connect simultaneously
- [ ] Error handling works for invalid messages
- [ ] Timeouts are handled gracefully

### Running Tests

```bash
# Run unit tests
python3 -m pytest tests/test_blackjack.py -v

# Run integration tests
python3 tests/test_integration.py

# Run web interface tests
python3 tests/test_web_integration.py
```

### Testing with Multiple Clients

```bash
# Terminal 1 - Start server
python3 src/blackjack_server.py

# Terminal 2 - First client
python3 src/blackjack_client.py

# Terminal 3 - Second client
python3 src/blackjack_client.py

# Terminal 4 - Third client
python3 src/blackjack_client.py
```

### Debug Mode

Add verbose logging by uncommenting debug prints or adding:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Network Analysis

Use Wireshark to inspect packets:
```bash
# Capture UDP broadcasts
sudo tcpdump -i any udp port 13122 -X

# Capture TCP game traffic
sudo tcpdump -i any tcp and host <server_ip> -X
```

## 🎮 Game Rules

### Card Values
- **Ace**: 11 points
- **2-10**: Face value
- **Jack, Queen, King**: 10 points each

### Round Flow
1. Player receives 2 cards (visible)
2. Dealer receives 2 cards (1 visible, 1 hidden)
3. Player repeatedly chooses Hit or Stand
4. If player busts (>21), dealer wins immediately
5. Dealer reveals hidden card
6. Dealer hits until reaching 17+
7. Compare totals to determine winner

### Dealer Strategy
- **Total < 17**: Must hit
- **Total ≥ 17**: Must stand

### Client Strategy (Default)
- **Total < 17**: Hit
- **Total ≥ 17**: Stand

## 📊 Statistics

Both client and server track:
- Total rounds played
- Wins, losses, and ties
- Win rate percentage
- Per-session and overall statistics

## 🏆 Excellence Criteria

To achieve top grades:
- ✅ Works with any client/server implementation
- ✅ High-quality, well-commented code
- ✅ Proper error handling and timeouts
- ✅ Clean code structure and organization
- ✅ No busy-waiting (efficient CPU usage)
- ✅ Regular Git commits by all team members
- ✅ Comprehensive testing

## 📝 Code Quality

### Naming Conventions
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Documentation
- Module docstrings explain purpose
- Class docstrings describe functionality
- Function docstrings include Args/Returns
- Inline comments explain complex logic

### Error Handling
- All network operations wrapped in try/except
- Timeouts on all socket operations
- Validation of all received messages
- Graceful degradation on errors

## 🤝 Contributing

When working in a team:
1. Use Git branches for features
2. Write descriptive commit messages
3. Review each other's code
4. Test thoroughly before committing
5. All members should contribute commits

## 📄 License

This project is created for educational purposes as part of the Intro to Computer Networks 2025 course.

## 👥 Authors

**Team Name**: DragonLion

**Members**:
Tal Rays 

---

**Good luck, and may your protocol never bust! 🎰**

