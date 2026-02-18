"""
WebSocket support for real-time build streaming.
"""
import asyncio
import json
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime


class BuildStreamManager:
    """Manages WebSocket connections for build streaming."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.send_message(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        })

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: Dict[str, Any]):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                print(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    async def stream_build_progress(self, client_id: str, build_id: str):
        """
        Stream build progress updates to a client.

        This is a placeholder that demonstrates the streaming pattern.
        In production, this would integrate with the ArchitectBuilder
        to send real-time updates during code generation.
        """
        # Simulate build phases
        phases = [
            {"phase": "initializing", "message": "Loading project manifest..."},
            {"phase": "planning", "message": "Parsing implementation plan..."},
            {"phase": "generating", "message": "Generating code files...", "progress": 0},
            {"phase": "generating", "message": "Generated file 1/3", "progress": 33},
            {"phase": "generating", "message": "Generated file 2/3", "progress": 66},
            {"phase": "generating", "message": "Generated file 3/3", "progress": 100},
            {"phase": "testing", "message": "Running tests..."},
            {"phase": "complete", "message": "Build completed successfully!"}
        ]

        for phase_data in phases:
            await self.send_message(client_id, {
                "type": "build_progress",
                "build_id": build_id,
                "timestamp": datetime.now().isoformat(),
                **phase_data
            })
            await asyncio.sleep(1)  # Simulate work


# Global instance
build_stream_manager = BuildStreamManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint handler for build streaming.

    Usage:
        Connect to ws://localhost:8000/ws/{client_id}
        Send JSON: {"action": "start_build", "build_id": "some-id"}
        Receive real-time build updates
    """
    await build_stream_manager.connect(websocket, client_id)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start_build":
                build_id = data.get("build_id", "unknown")
                await build_stream_manager.send_message(client_id, {
                    "type": "build_started",
                    "build_id": build_id,
                    "timestamp": datetime.now().isoformat()
                })

                # Start streaming build progress
                await build_stream_manager.stream_build_progress(client_id, build_id)

            elif action == "ping":
                await build_stream_manager.send_message(client_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

            else:
                await build_stream_manager.send_message(client_id, {
                    "type": "error",
                    "message": f"Unknown action: {action}"
                })

    except WebSocketDisconnect:
        build_stream_manager.disconnect(client_id)
        print(f"Client {client_id} disconnected")
    except Exception as e:
        print(f"WebSocket error for {client_id}: {e}")
        build_stream_manager.disconnect(client_id)
