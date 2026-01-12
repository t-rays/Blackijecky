# Web Interface Directory

## Overview

This directory contains the web-based user interface for the Blackjack game. The web interface provides a modern, visual way to play the game through a browser instead of using the terminal client.

## Files

### `web_interface.html`
**Purpose**: Main HTML page for the web interface

**Functionality**:
- Provides the structure and layout of the web interface
- Contains connection panel for server discovery
- Displays game area with dealer and player sections
- Shows game controls (Hit, Stand buttons)
- Displays statistics and round information

**Key Elements**:
- Connection form (name, rounds)
- Game panel with dealer/player hands
- Control buttons
- Status messages
- Loading overlay

### `web_script.js`
**Purpose**: Client-side JavaScript for game logic and API communication

**Functionality**:
- Handles server discovery via HTTP API
- Manages game session creation
- Implements Server-Sent Events (SSE) for real-time updates
- Renders cards and game state
- Handles user decisions (Hit/Stand)
- Updates UI based on game events
- Manages game state and statistics

**Key Functions**:
- `handleDiscover()` - Discovers available servers
- `createSession()` - Creates game session
- `handleGameEvent()` - Processes SSE events
- `handleDecision()` - Sends Hit/Stand decisions
- `renderHand()` - Displays cards
- `updateUI()` - Updates all UI elements

### `web_style.css`
**Purpose**: Styling and visual design

**Functionality**:
- Modern gradient design
- Card animations and styling
- Responsive layout (works on mobile)
- Color coding (red/black cards)
- Hidden card styling (dealer's hidden card)
- Button and form styling
- Status message styling

**Key Features**:
- Smooth card deal animations
- Hidden card with question mark
- Responsive design
- Modern UI/UX

## Instructions

### Setup
1. Make sure the blackjack server is running:
   ```bash
   python3 src/blackjack_server.py
   ```

2. Start the web bridge:
   ```bash
   python3 src/web_bridge.py
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:8080
   ```

### Using the Interface

1. **Connect to Server**:
   - Enter your name (optional, defaults to "WebPlayer")
   - Enter number of rounds (1-255)
   - Click "Discover Server"
   - Wait for connection

2. **Play the Game**:
   - Cards will appear automatically
   - Click "Hit" to get another card
   - Click "Stand" to end your turn
   - Watch dealer's turn automatically
   - See round results

3. **View Statistics**:
   - Wins, losses, and ties are displayed
   - Round number is shown
   - Final statistics after all rounds

### Features

- **Real-time Updates**: Cards appear instantly via SSE
- **Visual Cards**: Beautiful card display with suits and ranks
- **Hidden Card**: Dealer's hidden card shown as "?" until revealed
- **Animations**: Smooth card deal animations
- **Responsive**: Works on desktop and mobile devices
- **Statistics**: Live tracking of wins/losses/ties

## Architecture

The web interface communicates with the web bridge (`src/web_bridge.py`) via HTTP:
- **Discovery**: `GET /api/discover` - Find available servers
- **Session**: `POST /api/session/create` - Create game session
- **Decision**: `POST /api/session/decision` - Send Hit/Stand
- **Events**: `GET /api/session/events` - SSE stream for real-time updates

The web bridge then communicates with the TCP blackjack server using the standard protocol.

## Browser Compatibility

Works in all modern browsers:
- Chrome/Edge (recommended)
- Firefox
- Safari
- Mobile browsers

## Troubleshooting

- **Can't connect**: Make sure both server and web_bridge are running
- **Cards not appearing**: Check browser console for errors
- **Buttons disabled**: Wait for your turn or check game state
- **No server found**: Ensure server is broadcasting on the network

