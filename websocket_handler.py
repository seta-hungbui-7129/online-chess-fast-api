from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional, Set
import json
import asyncio
from datetime import datetime

from models import WebSocketMessage, Player, MoveRequest, GameStateResponse
from game_manager import GameManager
from clock_manager import clock_manager


class ConnectionManager:
    def __init__(self):
        # Store active connections per game
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        # Store player info per connection
        self.connection_players: Dict[WebSocket, str] = {}
        # Store game_id per connection
        self.connection_games: Dict[WebSocket, str] = {}
    
    async def connect(self, websocket: WebSocket, game_id: str, player_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        # Initialize game connections if not exists
        if game_id not in self.active_connections:
            self.active_connections[game_id] = {}
        
        # Store connection info
        self.active_connections[game_id][player_id] = websocket
        self.connection_players[websocket] = player_id
        self.connection_games[websocket] = game_id
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.connection_players:
            player_id = self.connection_players[websocket]
            game_id = self.connection_games[websocket]
            
            # Remove from active connections
            if game_id in self.active_connections and player_id in self.active_connections[game_id]:
                del self.active_connections[game_id][player_id]
            
            # Clean up empty game connections
            if game_id in self.active_connections and not self.active_connections[game_id]:
                del self.active_connections[game_id]
            
            # Remove connection tracking
            del self.connection_players[websocket]
            del self.connection_games[websocket]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            print(f"Error sending personal message: {e}")
    
    async def send_to_player(self, message: dict, game_id: str, player_id: str):
        """Send a message to a specific player in a game"""
        if game_id in self.active_connections and player_id in self.active_connections[game_id]:
            websocket = self.active_connections[game_id][player_id]
            await self.send_personal_message(message, websocket)
    
    async def broadcast_to_game(self, message: dict, game_id: str, exclude_player: Optional[str] = None):
        """Broadcast a message to all players in a game"""
        if game_id not in self.active_connections:
            return
        
        for player_id, websocket in self.active_connections[game_id].items():
            if exclude_player and player_id == exclude_player:
                continue
            
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error broadcasting to player {player_id}: {e}")
    
    def get_connected_players(self, game_id: str) -> List[str]:
        """Get list of connected player IDs for a game"""
        if game_id not in self.active_connections:
            return []
        return list(self.active_connections[game_id].keys())


class WebSocketHandler:
    def __init__(self, game_manager: GameManager):
        self.game_manager = game_manager
        self.connection_manager = ConnectionManager()
        
        # Set up clock callbacks
        clock_manager.set_callback = self._setup_clock_callback
    
    def _setup_clock_callback(self, game_id: str, callback):
        """Setup clock callback for a specific game"""
        async def clock_callback(event_type: str, data: dict):
            if event_type == "time_up":
                await self._handle_time_up(data["game_id"], data["player"])
            elif event_type == "clock_update":
                await self._handle_clock_update(data)
        
        clock_manager.callbacks[game_id] = clock_callback
    
    async def handle_websocket(self, websocket: WebSocket, game_id: str, player_id: str):
        """Main WebSocket handler"""
        await self.connection_manager.connect(websocket, game_id, player_id)
        
        try:
            # Send initial game state
            await self._send_game_state(game_id, player_id)
            
            # Notify other players that someone joined
            await self.connection_manager.broadcast_to_game(
                {
                    "event": "player_joined",
                    "data": {
                        "player_id": player_id,
                        "connected_players": self.connection_manager.get_connected_players(game_id)
                    }
                },
                game_id,
                exclude_player=player_id
            )
            
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Process the message
                await self._handle_message(websocket, game_id, player_id, message_data)
                
        except WebSocketDisconnect:
            self.connection_manager.disconnect(websocket)
            
            # Notify other players that someone left
            await self.connection_manager.broadcast_to_game(
                {
                    "event": "player_left",
                    "data": {
                        "player_id": player_id,
                        "connected_players": self.connection_manager.get_connected_players(game_id)
                    }
                },
                game_id
            )
        except Exception as e:
            print(f"WebSocket error: {e}")
            self.connection_manager.disconnect(websocket)
    
    async def _handle_message(self, websocket: WebSocket, game_id: str, player_id: str, message_data: dict):
        """Handle incoming WebSocket messages"""
        try:
            event = message_data.get("event")
            data = message_data.get("data", {})
            
            if event == "move":
                await self._handle_move(game_id, player_id, data)
            elif event == "undo":
                await self._handle_undo(game_id, player_id)
            elif event == "redo":
                await self._handle_redo(game_id, player_id)
            elif event == "join":
                # Already handled in main handler
                pass
            elif event == "get_state":
                await self._send_game_state(game_id, player_id)
            else:
                await self.connection_manager.send_personal_message(
                    {"event": "error", "data": {"message": f"Unknown event: {event}"}},
                    websocket
                )
        
        except Exception as e:
            await self.connection_manager.send_personal_message(
                {"event": "error", "data": {"message": str(e)}},
                websocket
            )
    
    async def _handle_move(self, game_id: str, player_id: str, data: dict):
        """Handle move events"""
        try:
            from_square = data.get("from")
            to_square = data.get("to")
            promotion = data.get("promotion")
            
            if not from_square or not to_square:
                raise ValueError("Missing from or to square")
            
            # Validate it's the player's turn
            game = self.game_manager.get_game_state(game_id)
            current_player = "white" if game.current_turn == "white" else "black"
            
            # Check if this player is allowed to make moves for current turn
            if ((current_player == "white" and game.white_player and game.white_player.id != player_id) or
                (current_player == "black" and game.black_player and game.black_player.id != player_id)):
                raise ValueError("Not your turn")
            
            # Make the move
            updated_game, move = self.game_manager.make_move(game_id, from_square, to_square, promotion)
            
            # Switch clock if game has time control
            if updated_game.clock:
                clock_manager.switch_turn(game_id)
            
            # Broadcast move to all players
            await self.connection_manager.broadcast_to_game(
                {
                    "event": "move_made",
                    "data": {
                        "move": {
                            "from": from_square,
                            "to": to_square,
                            "promotion": promotion,
                            "san": move.san_notation
                        },
                        "fen": updated_game.current_fen,
                        "current_turn": updated_game.current_turn,
                        "move_number": len(updated_game.move_history),
                        "status": updated_game.status.value,
                        "result": updated_game.result.value
                    }
                },
                game_id
            )
            
            # Check for game end
            if updated_game.status.value == "finished":
                await self._handle_game_over(game_id, updated_game.result.value)
        
        except Exception as e:
            await self.connection_manager.send_to_player(
                {"event": "move_error", "data": {"message": str(e)}},
                game_id,
                player_id
            )
    
    async def _handle_undo(self, game_id: str, player_id: str):
        """Handle undo events"""
        try:
            updated_game = self.game_manager.undo_move(game_id)
            
            # Broadcast undo to all players
            await self.connection_manager.broadcast_to_game(
                {
                    "event": "move_undone",
                    "data": {
                        "fen": updated_game.current_fen,
                        "current_turn": updated_game.current_turn,
                        "move_number": len(updated_game.move_history),
                        "status": updated_game.status.value,
                        "result": updated_game.result.value
                    }
                },
                game_id
            )
        
        except Exception as e:
            await self.connection_manager.send_to_player(
                {"event": "undo_error", "data": {"message": str(e)}},
                game_id,
                player_id
            )
    
    async def _handle_redo(self, game_id: str, player_id: str):
        """Handle redo events"""
        try:
            updated_game = self.game_manager.redo_move(game_id)
            
            # Broadcast redo to all players
            await self.connection_manager.broadcast_to_game(
                {
                    "event": "move_redone",
                    "data": {
                        "fen": updated_game.current_fen,
                        "current_turn": updated_game.current_turn,
                        "move_number": len(updated_game.move_history),
                        "status": updated_game.status.value,
                        "result": updated_game.result.value
                    }
                },
                game_id
            )
        
        except Exception as e:
            await self.connection_manager.send_to_player(
                {"event": "redo_error", "data": {"message": str(e)}},
                game_id,
                player_id
            )
    
    async def _send_game_state(self, game_id: str, player_id: str):
        """Send current game state to a player"""
        try:
            game = self.game_manager.get_game_state(game_id)
            legal_moves = self.game_manager.get_legal_moves(game_id)
            
            # Get clock state if available
            clock_state = None
            if game.clock:
                clock_state = clock_manager.get_clock_state(game_id)
            
            state_data = {
                "game": game.dict(),
                "legal_moves": legal_moves,
                "is_check": self.game_manager.is_check(game_id),
                "is_checkmate": self.game_manager.is_checkmate(game_id),
                "is_stalemate": self.game_manager.is_stalemate(game_id),
                "is_draw": self.game_manager.is_draw(game_id),
                "clock": clock_state.dict() if clock_state else None
            }
            
            await self.connection_manager.send_to_player(
                {"event": "game_state", "data": state_data},
                game_id,
                player_id
            )
        
        except Exception as e:
            await self.connection_manager.send_to_player(
                {"event": "error", "data": {"message": str(e)}},
                game_id,
                player_id
            )
    
    async def _handle_game_over(self, game_id: str, result: str):
        """Handle game over events"""
        await self.connection_manager.broadcast_to_game(
            {
                "event": "game_over",
                "data": {
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            game_id
        )
        
        # Stop the clock
        clock_manager.pause(game_id)
    
    async def _handle_time_up(self, game_id: str, player: str):
        """Handle time running out"""
        try:
            game = self.game_manager.get_game_state(game_id)
            if game.status.value == "active":
                # Set game result based on who ran out of time
                game.status = "finished"
                game.result = "black_wins" if player == "white" else "white_wins"
                
                await self.connection_manager.broadcast_to_game(
                    {
                        "event": "time_up",
                        "data": {
                            "player": player,
                            "result": game.result,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    },
                    game_id
                )
                
                await self._handle_game_over(game_id, game.result)
        
        except Exception as e:
            print(f"Error handling time up: {e}")
    
    async def _handle_clock_update(self, data: dict):
        """Handle clock update events"""
        game_id = data["game_id"]
        
        await self.connection_manager.broadcast_to_game(
            {
                "event": "clock_update",
                "data": {
                    "white_time": data["white_time"],
                    "black_time": data["black_time"],
                    "active_player": data["active_player"]
                }
            },
            game_id
        )


# Global WebSocket handler instance
websocket_handler = None
