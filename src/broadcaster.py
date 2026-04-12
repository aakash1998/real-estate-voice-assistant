import asyncio
import json
import websockets

# All connected dashboard clients
CLIENTS = set()

async def broadcast(message: dict):
    """Send event to all connected dashboard clients."""
    if CLIENTS:
        data = json.dumps(message)
        disconnected = set()
        for client in CLIENTS:
            try:
                await client.send(data)
            except Exception:
                disconnected.add(client)
        CLIENTS.difference_update(disconnected)

async def handler(websocket):
    """Handle new dashboard connection."""
    CLIENTS.add(websocket)
    print(f"[DASHBOARD] Client connected ({len(CLIENTS)} total)")
    try:
        await websocket.wait_closed()
    finally:
        CLIENTS.discard(websocket)
        print(f"[DASHBOARD] Client disconnected ({len(CLIENTS)} total)")

async def start_broadcaster():
    """Start WebSocket server for dashboard on port 8765."""
    server = await websockets.serve(handler, "localhost", 8765)
    print("[DASHBOARD] Broadcasting on ws://localhost:8765")
    return server