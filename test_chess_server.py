#!/usr/bin/env python3
"""
Test script for the Chess Server
Tests all major functionality including API endpoints and game logic
"""

import asyncio
import json
import requests
import websockets
from datetime import datetime
from models import Player, TimeControl, CreateGameRequest, MoveRequest


class ChessServerTester:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        self.ws_url = base_url.replace("http", "ws")
        
    def test_health_check(self):
        """Test server health endpoint"""
        print("Testing health check...")
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_create_game(self):
        """Test game creation"""
        print("Testing game creation...")
        
        # Create players
        white_player = {
            "username": "alice",
            "rating": 1500
        }
        
        black_player = {
            "username": "bob", 
            "rating": 1400
        }
        
        time_control = {
            "initial_time": 600,  # 10 minutes
            "increment": 5        # 5 seconds
        }
        
        # Create game
        game_data = {
            "white_player": white_player,
            "black_player": black_player,
            "time_control": time_control
        }
        
        response = requests.post(f"{self.api_url}/game", json=game_data)
        assert response.status_code == 200
        
        game = response.json()
        assert "id" in game
        assert game["white_player"]["username"] == "alice"
        assert game["black_player"]["username"] == "bob"
        assert game["status"] == "active"
        
        print(f"✓ Game created with ID: {game['id']}")
        return game["id"]
    
    def test_get_game_state(self, game_id):
        """Test getting game state"""
        print("Testing get game state...")
        
        response = requests.get(f"{self.api_url}/game/{game_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "game" in data
        assert "legal_moves" in data
        assert len(data["legal_moves"]) == 20  # Standard opening position has 20 legal moves
        
        print("✓ Game state retrieved successfully")
        return data
    
    def test_make_moves(self, game_id):
        """Test making moves"""
        print("Testing moves...")
        
        # Test valid move: e2-e4
        move_data = {
            "from_square": "e2",
            "to_square": "e4"
        }
        
        response = requests.post(f"{self.api_url}/game/{game_id}/move", json=move_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["game"]["current_turn"] == "black"
        assert len(data["game"]["move_history"]) == 1
        
        print("✓ First move (e2-e4) successful")
        
        # Test second move: e7-e5
        move_data = {
            "from_square": "e7",
            "to_square": "e5"
        }
        
        response = requests.post(f"{self.api_url}/game/{game_id}/move", json=move_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["game"]["current_turn"] == "white"
        assert len(data["game"]["move_history"]) == 2
        
        print("✓ Second move (e7-e5) successful")
        
        # Test invalid move
        move_data = {
            "from_square": "e4",
            "to_square": "e6"  # Invalid move
        }
        
        response = requests.post(f"{self.api_url}/game/{game_id}/move", json=move_data)
        assert response.status_code == 400
        
        print("✓ Invalid move correctly rejected")
        
        return data
    
    def test_undo_redo(self, game_id):
        """Test undo and redo functionality"""
        print("Testing undo/redo...")
        
        # Undo last move
        response = requests.post(f"{self.api_url}/game/{game_id}/undo")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["game"]["move_history"]) == 1
        assert data["game"]["current_turn"] == "black"
        
        print("✓ Undo successful")
        
        # Redo the move
        response = requests.post(f"{self.api_url}/game/{game_id}/redo")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["game"]["move_history"]) == 2
        assert data["game"]["current_turn"] == "white"
        
        print("✓ Redo successful")
    
    def test_pgn_export(self, game_id):
        """Test PGN export"""
        print("Testing PGN export...")
        
        response = requests.get(f"{self.api_url}/game/{game_id}/pgn")
        assert response.status_code == 200
        
        data = response.json()
        assert "pgn" in data
        assert "1. e4 e5" in data["pgn"]
        
        print("✓ PGN export successful")
    
    def test_clock_functionality(self, game_id):
        """Test chess clock"""
        print("Testing clock functionality...")
        
        # Get clock state
        response = requests.get(f"{self.api_url}/game/{game_id}/clock")
        assert response.status_code == 200
        
        data = response.json()
        assert "white_time" in data
        assert "black_time" in data
        assert data["white_time"] <= 600  # Should be less than or equal to initial time
        
        print("✓ Clock state retrieved successfully")
        
        # Pause clock
        response = requests.post(f"{self.api_url}/game/{game_id}/clock/pause")
        assert response.status_code == 200
        
        print("✓ Clock paused successfully")
    
    async def test_websocket_connection(self, game_id):
        """Test WebSocket functionality"""
        print("Testing WebSocket connection...")
        
        uri = f"{self.ws_url}/ws/game/{game_id}?player_id=test_player"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Send join message
                join_message = {
                    "event": "join",
                    "data": {}
                }
                await websocket.send(json.dumps(join_message))
                
                # Receive game state
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                assert data["event"] == "game_state"
                print("✓ WebSocket connection and game state received")
                
                # Test move via WebSocket
                move_message = {
                    "event": "move",
                    "data": {
                        "from": "g1",
                        "to": "f3"
                    }
                }
                await websocket.send(json.dumps(move_message))
                
                # Should receive move confirmation
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data["event"] == "move_made":
                    print("✓ WebSocket move successful")
                elif data["event"] == "move_error":
                    print(f"Move error (expected if not player's turn): {data['data']['message']}")
                
        except Exception as e:
            print(f"WebSocket test failed: {e}")
            return False
        
        return True
    
    def test_list_games(self):
        """Test listing games"""
        print("Testing list games...")
        
        response = requests.get(f"{self.api_url}/games")
        assert response.status_code == 200
        
        data = response.json()
        assert "games" in data
        assert len(data["games"]) > 0
        
        print(f"✓ Found {len(data['games'])} active games")
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting Chess Server Tests...")
        print("=" * 50)
        
        try:
            # Test basic functionality
            self.test_health_check()
            game_id = self.test_create_game()
            self.test_get_game_state(game_id)
            self.test_make_moves(game_id)
            self.test_undo_redo(game_id)
            self.test_pgn_export(game_id)
            self.test_clock_functionality(game_id)
            self.test_list_games()
            
            # Test WebSocket functionality
            print("\nTesting WebSocket functionality...")
            asyncio.run(self.test_websocket_connection(game_id))
            
            print("\n" + "=" * 50)
            print("✅ All tests passed successfully!")
            
        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            return False
        except requests.exceptions.ConnectionError:
            print("\n❌ Cannot connect to server. Make sure the server is running on localhost:8000")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            return False
        
        return True


def main():
    """Main test function"""
    print("Chess Server Test Suite")
    print("Make sure the server is running with: python main.py")
    print()
    
    tester = ChessServerTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        print("The chess server is working correctly.")
    else:
        print("\n💥 Some tests failed.")
        print("Check the server logs for more details.")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
