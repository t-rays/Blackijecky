#!/usr/bin/env python3
"""
Manual test script to verify web interface is working
Run this while web_bridge.py is running to test the API
"""

import http.client
import json
import time

def test_web_interface():
    """Test web interface endpoints manually."""
    print("="*60)
    print("MANUAL WEB INTERFACE TEST")
    print("="*60)
    print("\nMake sure web_bridge.py is running on port 8080")
    print("="*60)
    
    try:
        conn = http.client.HTTPConnection('localhost', 8080, timeout=5)
        
        # Test 1: Discover server
        print("\n1. Testing server discovery...")
        conn.request('GET', '/api/discover')
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        print(f"   Response: {json.dumps(data, indent=2)}")
        
        if not data.get('success'):
            print("   ⚠ No server found. Start blackjack_server.py first.")
            conn.close()
            return
        
        server_ip = data['server_ip']
        tcp_port = data['tcp_port']
        print(f"   ✓ Found server: {data['server_name']} at {server_ip}:{tcp_port}")
        
        # Test 2: Create session
        print("\n2. Testing session creation...")
        conn.request('POST', '/api/session/create',
                    json.dumps({
                        'server_ip': server_ip,
                        'tcp_port': tcp_port,
                        'num_rounds': 1,
                        'client_name': 'TestPlayer'
                    }),
                    {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        print(f"   Response: {json.dumps(data, indent=2)}")
        
        if not data.get('success'):
            print(f"   ✗ Session creation failed: {data.get('error')}")
            conn.close()
            return
        
        session_id = data['session_id']
        print(f"   ✓ Session created: {session_id}")
        
        # Test 3: Get initial state
        print("\n3. Testing get state...")
        time.sleep(1)  # Give server time to receive initial cards
        conn.request('GET', f'/api/session/state?session_id={session_id}')
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        state = data.get('state', {})
        print(f"   Game state: {state.get('game_state')}")
        print(f"   Player hand: {len(state.get('player_hand', []))} cards")
        print(f"   Dealer hand: {len(state.get('dealer_hand', []))} cards")
        print(f"   Player total: {state.get('player_total', 0)}")
        
        if len(state.get('player_hand', [])) < 2:
            print("   ⚠ Initial cards not received yet. Wait a moment...")
            time.sleep(2)
            conn.request('GET', f'/api/session/state?session_id={session_id}')
            response = conn.getresponse()
            data = json.loads(response.read().decode())
            state = data.get('state', {})
            print(f"   After wait - Player hand: {len(state.get('player_hand', []))} cards")
            print(f"   After wait - Dealer hand: {len(state.get('dealer_hand', []))} cards")
        
        # Test 4: Send decision
        if state.get('game_state') == 'waiting_decision':
            print("\n4. Testing send decision (Stand)...")
            conn.request('POST', '/api/session/decision',
                        json.dumps({
                            'session_id': session_id,
                            'decision': 'Stand'
                        }),
                        {'Content-Type': 'application/json'})
            response = conn.getresponse()
            data = json.loads(response.read().decode())
            print(f"   Response: {json.dumps(data, indent=2)}")
            
            if data.get('success'):
                print("   ✓ Decision sent successfully")
            else:
                print(f"   ✗ Decision failed: {data.get('error')}")
        
        conn.close()
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        print("\nIf all tests passed, the web interface should work!")
        print("Open http://localhost:8080 in your browser.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_web_interface()

