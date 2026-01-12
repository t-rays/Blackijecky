"""
TCP utility functions for handling fixed-size protocol messages.
"""

import socket


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Receive exactly n bytes from socket.
    
    Args:
        sock: Socket to receive from
        n: Number of bytes to receive
        
    Returns:
        Exactly n bytes, or empty bytes if connection closed
        
    Raises:
        socket.error: If socket error occurs
    """
    data = b''
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            # Connection closed
            return b''
        data += chunk
    return data

