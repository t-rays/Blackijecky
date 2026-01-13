// Blackjack Web Interface - JavaScript

const API_BASE = window.location.origin;
let currentSessionId = null;
let eventSource = null;  // SSE connection
let eventBuffer = [];  // Buffer for events during round end message
let gameState = {
    currentRound: 0,
    totalRounds: 1,
    playerHand: [],
    dealerHand: [],
    playerTotal: 0,
    dealerTotal: 0,
    wins: 0,
    losses: 0,
    ties: 0,
    gameState: 'disconnected'
};

// DOM Elements
const connectionPanel = document.getElementById('connection-panel');
const gamePanel = document.getElementById('game-panel');
const discoverBtn = document.getElementById('discover-btn');
const discoverStatus = document.getElementById('discover-status');
const hitBtn = document.getElementById('hit-btn');
const standBtn = document.getElementById('stand-btn');
const newGameBtn = document.getElementById('new-game-btn');
const loadingOverlay = document.getElementById('loading-overlay');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('Web interface initialized');
    discoverBtn.addEventListener('click', handleDiscover);
    hitBtn.addEventListener('click', () => handleDecision('Hitt'));
    standBtn.addEventListener('click', () => handleDecision('Stand'));
    newGameBtn.addEventListener('click', resetGame);
    
    // Check if API is accessible
    fetch(`${API_BASE}/api/discover`)
        .then(() => console.log('API is accessible'))
        .catch(err => console.error('API not accessible:', err));
});

// Server Discovery
async function handleDiscover() {
    showLoading(true);
    discoverStatus.textContent = 'Discovering server...';
    discoverStatus.className = 'status info';
    console.log('Starting server discovery...');
    
    try {
        const response = await fetch(`${API_BASE}/api/discover`);
        console.log('Discovery response status:', response.status);
        const data = await response.json();
        console.log('Discovery response data:', data);
        
        if (data.success) {
            discoverStatus.textContent = `Found server: ${data.server_name} at ${data.server_ip}:${data.tcp_port}`;
            discoverStatus.className = 'status success';
            console.log('Server discovered, creating session...');
            
            // Auto-create session
            await createSession(data.server_ip, data.tcp_port);
        } else {
            discoverStatus.textContent = `Error: ${data.error}`;
            discoverStatus.className = 'status error';
            console.error('Discovery failed:', data.error);
        }
    } catch (error) {
        discoverStatus.textContent = `Connection error: ${error.message}`;
        discoverStatus.className = 'status error';
        console.error('Discovery error:', error);
    } finally {
        showLoading(false);
    }
}

// Create Game Session
async function createSession(serverIp, tcpPort) {
    const clientName = document.getElementById('client-name').value || 'WebPlayer';
    const numRounds = parseInt(document.getElementById('num-rounds').value) || 1;
    
    showLoading(true);
    
    try {
        const response = await fetch(`${API_BASE}/api/session/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                server_ip: serverIp,
                tcp_port: tcpPort,
                num_rounds: numRounds,
                client_name: clientName
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentSessionId = data.session_id;
            console.log('Session created successfully:', currentSessionId);
            connectionPanel.classList.add('hidden');
            gamePanel.classList.remove('hidden');
            
            gameState.totalRounds = numRounds;
            gameState.currentRound = 1;
            
            updateUI();
            updateGameStatus('Connecting to game...', 'info');
            
            // Start SSE stream for real-time updates
            // Give a moment for TCP connection to establish
            setTimeout(() => {
                startSSEStream();
            }, 500);
        } else {
            const errorMsg = `Error creating session: ${data.error}`;
            discoverStatus.textContent = errorMsg;
            discoverStatus.className = 'status error';
            console.error('Session creation failed:', data.error);
            updateGameStatus(errorMsg, 'error');
        }
    } catch (error) {
        discoverStatus.textContent = `Error: ${error.message}`;
        discoverStatus.className = 'status error';
    } finally {
        showLoading(false);
    }
}

// Start Server-Sent Events stream
function startSSEStream() {
    if (!currentSessionId) {
        console.error('No session ID for SSE stream');
        return;
    }
    
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
    }
    
    console.log('Starting SSE stream for session:', currentSessionId);
    
    // Create new SSE connection
    eventSource = new EventSource(`${API_BASE}/api/session/events?session_id=${currentSessionId}`);
    
    eventSource.onopen = function() {
        console.log('SSE connection opened');
        updateGameStatus('Connected to game server...', 'info');
    };
    
    eventSource.onmessage = function(event) {
        try {
            // Skip keepalive messages
            if (event.data.trim() === '' || event.data.startsWith(':')) {
                return;
            }
            
            const data = JSON.parse(event.data);
            console.log('SSE event received:', data);
            
            // If round end message is being shown, buffer events (except the finished event itself)
            if (roundEndMessageShown && data.state && data.state.game_state !== 'finished') {
                console.log('Buffering event during round end message:', data.state.game_state);
                eventBuffer.push(data);
                return;
            }
            
            handleGameEvent(data);
        } catch (error) {
            console.error('Error parsing SSE data:', error, event.data);
        }
    };
    
    eventSource.onerror = function(error) {
        console.error('SSE connection error:', error);
        updateGameStatus('Connection error. Reconnecting...', 'warning');
        // Try to reconnect after a delay
        setTimeout(() => {
            if (currentSessionId && eventSource.readyState === EventSource.CLOSED) {
                console.log('Attempting to reconnect SSE...');
                startSSEStream();
            }
        }, 2000);
    };
}

// Handle game events from SSE
function handleGameEvent(data) {
    if (data.error) {
        // Check if it's a connection closed error
        if (data.error === 'Connection closed') {
            // Check if all rounds are complete
            if (gameState.currentRound >= gameState.totalRounds && gameState.gameState === 'finished') {
                console.log('Connection closed after game completion - showing game complete screen');
                roundEndMessageShown = false;
                showGameComplete();
                return;
            } else {
                // Connection closed unexpectedly during the game
                console.error('Connection closed unexpectedly during round', gameState.currentRound, 'of', gameState.totalRounds);
                // Check if we have cards - if so, the connection might have closed after receiving cards
                // In that case, show a less alarming message
                if (gameState.playerHand && gameState.playerHand.length > 0) {
                    updateGameStatus('Connection lost, but your cards were received. The game may continue. If issues persist, refresh the page.', 'warning');
                } else {
                    updateGameStatus('Connection lost. Please refresh the page to start a new game.', 'error');
                }
                hitBtn.disabled = true;
                standBtn.disabled = true;
                return;
            }
        }
        updateGameStatus(`Error: ${data.error}`, 'error');
        console.error('Game event error:', data.error);
        return;
    }
    
    // Update game state from event
    if (data.state) {
        const oldState = gameState.gameState;
        const newState = data.state.game_state || gameState.gameState;
        
        // Always trust the server's state - it has the authoritative game state
        // The server sends complete state with each event, so we should use it
        // Note: When processing buffered events, each event has a snapshot of state at that moment
        // This is correct - we'll see incremental updates (1 card, then 2, then dealer card)
        gameState = {
            currentRound: data.state.current_round !== undefined ? data.state.current_round : gameState.currentRound,
            totalRounds: data.state.num_rounds !== undefined ? data.state.num_rounds : gameState.totalRounds,
            // Always use server's hand data - it's always correct
            // For buffered events, each event has the state at that moment (incremental updates are expected)
            playerHand: Array.isArray(data.state.player_hand) ? data.state.player_hand : (gameState.playerHand || []),
            dealerHand: Array.isArray(data.state.dealer_hand) ? data.state.dealer_hand : (gameState.dealerHand || []),
            playerTotal: data.state.player_total !== undefined ? data.state.player_total : gameState.playerTotal,
            dealerTotal: data.state.dealer_total !== undefined ? data.state.dealer_total : gameState.dealerTotal,
            wins: data.state.session_wins !== undefined ? data.state.session_wins : gameState.wins,
            losses: data.state.session_losses !== undefined ? data.state.session_losses : gameState.losses,
            ties: data.state.session_ties !== undefined ? data.state.session_ties : gameState.ties,
            gameState: newState
        };
        
        // If transitioning from finished to playing, it's a new round - show message
        // But only if we haven't already called handleRoundEnd (to avoid overwriting the message)
        if (oldState === 'finished' && newState === 'playing') {
            console.log(`New round ${gameState.currentRound} starting!`);
            // Don't immediately update status - let handleRoundEnd show the message first
            // The status will be updated when the round actually starts (waiting_decision state)
        }
        
        console.log('Game state updated:', {
            state: gameState.gameState,
            playerHand: gameState.playerHand.length,
            dealerHand: gameState.dealerHand.length,
            playerTotal: gameState.playerTotal
        });
        
        updateUI();
        
        // Handle game state changes
        if (data.state.game_state === 'finished') {
            // Get round result from state or from result code
            let roundResult = data.state.round_result;
            if (!roundResult && data.result !== undefined) {
                // Fallback: derive from result code if round_result not in state
                if (data.result === 3) roundResult = 'WIN';
                else if (data.result === 2) roundResult = 'LOSS';
                else if (data.result === 1) roundResult = 'TIE';
            }
            console.log('Round finished, result:', roundResult, 'data:', data);
            
            // Check if this is the last round
            const currentRound = data.state.current_round || gameState.currentRound;
            const totalRounds = data.state.num_rounds || gameState.totalRounds;
            const isLastRound = currentRound >= totalRounds;
            
            if (isLastRound) {
                // Last round - show round end message, then game complete after delay
                handleRoundEnd(roundResult);
                // After showing round end message, show game complete
                setTimeout(() => {
                    roundEndMessageShown = false;
                    showGameComplete();
                }, 3000);
            } else {
                // More rounds to play
                handleRoundEnd(roundResult);
                // Hide summary before next round starts
                roundEndMessageTimeout = setTimeout(() => {
                    hideRoundSummary();
                }, 3000);
            }
            // Don't close SSE connection - keep it open for multiple rounds
            // The connection will close when all rounds are complete or on error
        } else if (data.state.game_state === 'waiting_decision') {
            hitBtn.disabled = false;
            standBtn.disabled = false;
            // Always update status for waiting_decision - this means the round has actually started
            // Clear the round end message flag if it's still set (round has started)
            if (roundEndMessageShown) {
                roundEndMessageShown = false;
                if (roundEndMessageTimeout) {
                    clearTimeout(roundEndMessageTimeout);
                    roundEndMessageTimeout = null;
                }
            }
            // Force status update - bypass the protection since we just cleared the flag
            // This ensures "Hitting..." or "You stand..." messages are replaced
            // Always update status when waiting_decision state is reached
            const statusEl = document.getElementById('game-status');
            if (statusEl) {
                statusEl.textContent = 'Your turn! Hit or Stand?';
                statusEl.className = 'status-info';
                console.log('Status updated to: Your turn! Hit or Stand?');
            } else {
                console.error('Status element not found!');
            }
        } else if (data.state.game_state === 'dealer_turn') {
            hitBtn.disabled = true;
            standBtn.disabled = true;
            // Only update status if round end message isn't being shown
            if (!roundEndMessageShown) {
                updateGameStatus('Dealer\'s turn...', 'info');
            }
        } else if (data.state.game_state === 'playing') {
            // Still receiving initial cards - only update if not showing round end message
            if (!roundEndMessageShown) {
                updateGameStatus('Receiving cards...', 'info');
            }
        }
    }
    
    // Show card animation if new card received
    if (data.card) {
        console.log('Card received:', data.card.display);
        // Card will appear via UI update
    }
}

// Note: Initial cards and all updates now come via SSE stream
// No need for polling receiveCard() function anymore

// Handle Player Decision
async function handleDecision(decision) {
    if (!currentSessionId) {
        console.error('No session ID for decision');
        return;
    }
    
    console.log(`Sending decision: ${decision}`);
    console.log(`Session ID: ${currentSessionId}`);
    console.log(`API Base: ${API_BASE}`);
    hitBtn.disabled = true;
    standBtn.disabled = true;
    
    try {
        const requestBody = {
            session_id: currentSessionId,
            decision: decision
        };
        console.log('Decision request body:', requestBody);
        
        console.log('About to send fetch request...');
        const fetchPromise = fetch(`${API_BASE}/api/session/decision`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        
        console.log('Fetch promise created, waiting for response...');
        const response = await Promise.race([
            fetchPromise,
            new Promise((_, reject) => 
                setTimeout(() => reject(new Error('Fetch timeout after 5 seconds')), 5000)
            )
        ]);
        
        console.log('Decision response status:', response.status, response.statusText);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Decision response error:', errorText);
            throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('Decision response:', data);
        
        if (data.success) {
            if (decision === 'Stand') {
                updateGameStatus('You stand. Waiting for dealer...', 'info');
                // Dealer cards will come via SSE automatically
            } else {
                // Hit - new card will come via SSE automatically
                // Don't set status here - it will update when the card arrives via SSE
                // The status will update to "Your turn! Hit or Stand?" when state becomes waiting_decision
            }
            // Don't re-enable buttons here - SSE will handle state updates
            // The game state will update via SSE events
        } else {
            updateGameStatus(`Error: ${data.error}`, 'error');
            hitBtn.disabled = false;
            standBtn.disabled = false;
        }
    } catch (error) {
        console.error('Decision error:', error);
        updateGameStatus(`Error: ${error.message}`, 'error');
        hitBtn.disabled = false;
        standBtn.disabled = false;
    }
}

// Dealer turn is now handled automatically via SSE stream
// Cards appear in real-time as they're received

// Handle Round End
let roundEndMessageShown = false;
let roundEndMessageTimeout = null;

function handleRoundEnd(result) {
    hitBtn.disabled = true;
    standBtn.disabled = true;
    
    let message = '';
    let statusClass = 'info';
    
    if (result === 'WIN') {
        message = '🎉 You WIN this round!';
        statusClass = 'success';
    } else if (result === 'LOSS') {
        message = '💔 You LOSE this round.';
        statusClass = 'error';
    } else if (result === 'TIE') {
        message = '🤝 It\'s a TIE!';
        statusClass = 'warning';
    }
    
    // Show round summary with all cards
    showRoundSummary(result);
    
    // Set flag to prevent status updates from overwriting the message
    roundEndMessageShown = true;
    
    // Clear any existing timeout
    if (roundEndMessageTimeout) {
        clearTimeout(roundEndMessageTimeout);
    }
    
    updateGameStatus(message, statusClass);
    
    // Check if more rounds
    if (gameState.currentRound < gameState.totalRounds) {
        roundEndMessageTimeout = setTimeout(() => {
            roundEndMessageShown = false;
            
            // Hide summary before processing new round events
            hideRoundSummary();
            
            // Process any buffered events from the new round
            console.log(`Processing ${eventBuffer.length} buffered events`);
            const bufferedEvents = [...eventBuffer]; // Copy array
            eventBuffer.length = 0; // Clear buffer
            
            // Process all buffered events
            for (const bufferedEvent of bufferedEvents) {
                handleGameEvent(bufferedEvent);
            }
            
            // Ensure status is correct after processing - if we're in waiting_decision, update status
            if (gameState.gameState === 'waiting_decision') {
                const statusEl = document.getElementById('game-status');
                if (statusEl) {
                    statusEl.textContent = 'Your turn! Hit or Stand?';
                    statusEl.className = 'status-info';
                }
                hitBtn.disabled = false;
                standBtn.disabled = false;
                console.log('Status updated after processing buffered events: Your turn! Hit or Stand?');
            }
            
            // Don't call startNextRound() here - the buffered events have already set up the new round
            // Calling startNextRound() would clear the hands that were just set by the buffered events!
            // The UI is already updated by handleGameEvent() -> updateUI() for each buffered event
        }, 3000);
    } else {
        // Game complete
        roundEndMessageTimeout = setTimeout(() => {
            roundEndMessageShown = false;
            
            // Process any buffered events
            console.log(`Processing ${eventBuffer.length} buffered events`);
            while (eventBuffer.length > 0) {
                const bufferedEvent = eventBuffer.shift();
                handleGameEvent(bufferedEvent);
            }
            
            // Keep summary visible for final round, but hide it when showing game complete
            setTimeout(() => {
                hideRoundSummary();
                showGameComplete();
            }, 2000);
        }, 3000);
    }
}

// Start Next Round
async function startNextRound() {
    // Clear the round end message flag so status updates can happen again
    roundEndMessageShown = false;
    
    // Hide round summary
    hideRoundSummary();
    
    // Don't increment currentRound here - it's already updated from SSE events
    // Just reset hands (they're already reset by the server, but ensure UI is clean)
    gameState.playerHand = [];
    gameState.dealerHand = [];
    gameState.playerTotal = 0;
    gameState.dealerTotal = 0;
    
    updateUI();
    
    // Only update status if we're actually starting (not just receiving cards)
    // The status will be updated when state becomes 'waiting_decision'
    // updateGameStatus(`Starting round ${gameState.currentRound}...`, 'info');
    
    // Cards will arrive automatically via SSE stream
    // No need to manually request them or reopen connection
    // SSE connection stays open for the entire session
}

// Show Game Complete
function showGameComplete() {
    const winRate = gameState.totalRounds > 0 
        ? ((gameState.wins / gameState.totalRounds) * 100).toFixed(1) 
        : 0;
    
    const message = `Game Complete! Win Rate: ${winRate}% (${gameState.wins}W-${gameState.losses}L-${gameState.ties}T)`;
    updateGameStatus(message, 'success');
    
    newGameBtn.classList.remove('hidden');
}

// Show Round Summary
function showRoundSummary(result) {
    const summaryEl = document.getElementById('round-summary');
    const playerCardsEl = document.getElementById('summary-player-cards');
    const dealerCardsEl = document.getElementById('summary-dealer-cards');
    const playerTotalEl = document.getElementById('summary-player-total');
    const dealerTotalEl = document.getElementById('summary-dealer-total');
    const resultEl = document.getElementById('summary-result');
    
    if (!summaryEl) return;
    
    // Clear previous cards
    playerCardsEl.innerHTML = '';
    dealerCardsEl.innerHTML = '';
    
    // Show all player cards
    gameState.playerHand.forEach(card => {
        const cardEl = createCardElement(card);
        playerCardsEl.appendChild(cardEl);
    });
    
    // Show all dealer cards (they're all visible now)
    gameState.dealerHand.forEach(card => {
        const cardEl = createCardElement(card);
        dealerCardsEl.appendChild(cardEl);
    });
    
    // Update totals
    playerTotalEl.textContent = gameState.playerTotal;
    dealerTotalEl.textContent = gameState.dealerTotal;
    
    // Update result
    resultEl.className = 'summary-result ' + result.toLowerCase();
    if (result === 'WIN') {
        resultEl.textContent = '🎉 You WIN!';
    } else if (result === 'LOSS') {
        resultEl.textContent = '💔 You LOSE';
    } else {
        resultEl.textContent = '🤝 It\'s a TIE!';
    }
    
    // Show summary
    summaryEl.classList.remove('hidden');
}

// Hide Round Summary
function hideRoundSummary() {
    const summaryEl = document.getElementById('round-summary');
    if (summaryEl) {
        summaryEl.classList.add('hidden');
    }
}

// Reset Game
function resetGame() {
    // Close SSE connection
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    currentSessionId = null;
    gameState = {
        currentRound: 0,
        totalRounds: 1,
        playerHand: [],
        dealerHand: [],
        playerTotal: 0,
        dealerTotal: 0,
        wins: 0,
        losses: 0,
        ties: 0,
        gameState: 'disconnected'
    };
    
    gamePanel.classList.add('hidden');
    connectionPanel.classList.remove('hidden');
    newGameBtn.classList.add('hidden');
    discoverStatus.textContent = '';
    discoverStatus.className = 'status';
    
    // Hide summary
    hideRoundSummary();
}

// Update UI
function updateUI() {
    // Update round info
    document.getElementById('round-number').textContent = gameState.currentRound;
    document.getElementById('total-rounds').textContent = gameState.totalRounds;
    
    // Update stats
    document.getElementById('wins-count').textContent = gameState.wins;
    document.getElementById('losses-count').textContent = gameState.losses;
    document.getElementById('ties-count').textContent = gameState.ties;
    
    // Update totals
    const playerTotalEl = document.getElementById('player-total');
    playerTotalEl.textContent = gameState.playerTotal;
    playerTotalEl.parentElement.className = 'total' + 
        (gameState.playerTotal > 21 ? ' bust' : '') +
        (gameState.playerTotal === 21 ? ' win' : '');
    
    const dealerTotalEl = document.getElementById('dealer-total');
    dealerTotalEl.textContent = gameState.dealerTotal;
    dealerTotalEl.parentElement.className = 'total' + 
        (gameState.dealerTotal > 21 ? ' bust' : '') +
        (gameState.dealerTotal === 21 ? ' win' : '');
    
    // Update hands
    renderHand('player-hand', gameState.playerHand);
    renderHand('dealer-hand', gameState.dealerHand);
}

// Render Hand
function renderHand(handId, hand) {
    const handEl = document.getElementById(handId);
    handEl.innerHTML = '';
    
    if (hand.length === 0) {
        handEl.innerHTML = '<div class="hand-placeholder">Waiting for cards...</div>';
        return;
    }
    
    // Special handling for dealer's hand: show hidden card if dealer has 2 cards but only 1 is visible
    if (handId === 'dealer-hand') {
        const isDealerTurn = gameState.gameState === 'dealer_turn' || gameState.gameState === 'finished';
        
        // Always show all dealer cards when game is finished (so you can see what the hidden card was)
        if (gameState.gameState === 'finished') {
            // Show all cards that we have
            hand.forEach(card => {
                const cardEl = createCardElement(card);
                handEl.appendChild(cardEl);
            });
        }
        // If dealer has 1 card and it's not dealer's turn yet, show hidden card placeholder
        else if (hand.length === 1 && !isDealerTurn) {
            // Show the visible card
            const cardEl = createCardElement(hand[0]);
            handEl.appendChild(cardEl);
            
            // Show hidden card placeholder
            const hiddenCardEl = createHiddenCardElement();
            handEl.appendChild(hiddenCardEl);
        } else {
            // Show all cards normally (dealer's turn or all cards visible)
            hand.forEach(card => {
                const cardEl = createCardElement(card);
                handEl.appendChild(cardEl);
            });
        }
    } else {
        // Player's hand: show all cards normally
        hand.forEach(card => {
            const cardEl = createCardElement(card);
            handEl.appendChild(cardEl);
        });
    }
}

// Create Card Element
function createCardElement(card) {
    const cardEl = document.createElement('div');
    cardEl.className = 'card';
    
    // Determine if red or black
    const isRed = card.suit === 0 || card.suit === 1; // Hearts or Diamonds
    cardEl.classList.add(isRed ? 'red' : 'black');
    
    cardEl.innerHTML = `
        <div class="card-rank">${card.rank_name}</div>
        <div class="card-suit">${card.suit_symbol}</div>
        <div class="card-value">${card.value}</div>
    `;
    
    return cardEl;
}

// Create Hidden Card Element (card back with question mark)
function createHiddenCardElement() {
    const cardEl = document.createElement('div');
    cardEl.className = 'card card-hidden';
    
    cardEl.innerHTML = `
        <div class="card-back-pattern"></div>
        <div class="card-question">?</div>
    `;
    
    return cardEl;
}

// Update Game Status
function updateGameStatus(message, type = 'info') {
    // Don't update status if round end message is being shown (unless it's the round end message itself)
    // Check if this is a round end message by looking for emojis or specific text
    const isRoundEndMessage = message.includes('🎉') || message.includes('💔') || message.includes('🤝') ||
                              message.includes('WIN this round') || message.includes('LOSE this round') || message.includes('TIE');
    
    if (roundEndMessageShown && !isRoundEndMessage) {
        return;
    }
    const statusEl = document.getElementById('game-status');
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;
}

// Utility Functions
function showLoading(show) {
    if (show) {
        loadingOverlay.classList.remove('hidden');
    } else {
        loadingOverlay.classList.add('hidden');
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

