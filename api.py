from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime

from models import (
    Game, Player, Move, CreateGameRequest, MoveRequest,
    GameStateResponse, TimeControl, GameStatus
)
from game_manager import GameManager
from clock_manager import clock_manager
from exceptions import (
    ChessServerException, GameNotFoundException, InvalidMoveException,
    GameStateException, PlayerException, ClockException, ValidationException
)


# Create router for API endpoints
router = APIRouter()

# Global game manager instance
game_manager = GameManager()


@router.post("/game", response_model=Game)
async def create_game(request: CreateGameRequest):
    """Create a new chess game"""
    try:
        # Create the game
        game = game_manager.create_game(
            white_player=request.white_player,
            black_player=request.black_player,
            time_control=request.time_control
        )
        
        # Set up clock if time control is provided
        if request.time_control:
            clock_manager.create_clock(game.id, request.time_control)
            
            # Start the clock for white player if both players are present
            if game.white_player and game.black_player:
                clock_manager.start(game.id, "white")
        
        return game
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/game/{game_id}", response_model=GameStateResponse)
async def get_game_state(game_id: str):
    """Get current game state"""
    try:
        game = game_manager.get_game_state(game_id)
        legal_moves = game_manager.get_legal_moves(game_id)
        
        # Create response with additional game state info
        response = GameStateResponse(
            game=game,
            legal_moves=legal_moves,
            is_check=game_manager.is_check(game_id),
            is_checkmate=game_manager.is_checkmate(game_id),
            is_stalemate=game_manager.is_stalemate(game_id),
            is_draw=game_manager.is_draw(game_id)
        )
        
        return response
    
    except GameNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/move", response_model=GameStateResponse)
async def make_move(game_id: str, move_request: MoveRequest):
    """Make a move in the game"""
    try:
        # Make the move
        updated_game, move = game_manager.make_move(
            game_id=game_id,
            from_square=move_request.from_square,
            to_square=move_request.to_square,
            promotion=move_request.promotion
        )
        
        # Switch clock if game has time control
        if updated_game.clock:
            clock_manager.switch_turn(game_id)
        
        # Get updated game state
        legal_moves = game_manager.get_legal_moves(game_id)
        
        response = GameStateResponse(
            game=updated_game,
            legal_moves=legal_moves,
            is_check=game_manager.is_check(game_id),
            is_checkmate=game_manager.is_checkmate(game_id),
            is_stalemate=game_manager.is_stalemate(game_id),
            is_draw=game_manager.is_draw(game_id)
        )
        
        return response
    
    except (InvalidMoveException, GameStateException, ValidationException) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GameNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/undo", response_model=GameStateResponse)
async def undo_move(game_id: str):
    """Undo the last move"""
    try:
        updated_game = game_manager.undo_move(game_id)
        legal_moves = game_manager.get_legal_moves(game_id)
        
        response = GameStateResponse(
            game=updated_game,
            legal_moves=legal_moves,
            is_check=game_manager.is_check(game_id),
            is_checkmate=game_manager.is_checkmate(game_id),
            is_stalemate=game_manager.is_stalemate(game_id),
            is_draw=game_manager.is_draw(game_id)
        )
        
        return response
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/redo", response_model=GameStateResponse)
async def redo_move(game_id: str):
    """Redo a previously undone move"""
    try:
        updated_game = game_manager.redo_move(game_id)
        legal_moves = game_manager.get_legal_moves(game_id)
        
        response = GameStateResponse(
            game=updated_game,
            legal_moves=legal_moves,
            is_check=game_manager.is_check(game_id),
            is_checkmate=game_manager.is_checkmate(game_id),
            is_stalemate=game_manager.is_stalemate(game_id),
            is_draw=game_manager.is_draw(game_id)
        )
        
        return response
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/join", response_model=Game)
async def join_game(game_id: str, player: Player):
    """Join a game as the second player"""
    try:
        updated_game = game_manager.join_game(game_id, player)
        
        # Start the clock if time control is set and both players are now present
        if updated_game.time_control and updated_game.white_player and updated_game.black_player:
            clock_manager.start(game_id, "white")
        
        return updated_game
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/game/{game_id}/pgn")
async def get_pgn(game_id: str):
    """Get PGN representation of the game"""
    try:
        pgn = game_manager.get_pgn(game_id)
        return {"pgn": pgn}
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/game/{game_id}/clock")
async def get_clock_state(game_id: str):
    """Get current clock state"""
    try:
        clock_state = clock_manager.get_clock_state(game_id)
        if clock_state is None:
            raise HTTPException(status_code=404, detail="Clock not found for this game")
        
        return {
            "white_time": clock_state.white_time,
            "black_time": clock_state.black_time,
            "active_player": clock_state.active_player,
            "last_move_time": clock_state.last_move_time,
            "white_time_formatted": clock_manager.get_formatted_time(clock_state.white_time),
            "black_time_formatted": clock_manager.get_formatted_time(clock_state.black_time)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/clock/pause")
async def pause_clock(game_id: str):
    """Pause the game clock"""
    try:
        success = clock_manager.pause(game_id)
        if not success:
            raise HTTPException(status_code=404, detail="Clock not found for this game")
        
        return {"message": "Clock paused successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/game/{game_id}/clock/resume")
async def resume_clock(game_id: str, player: str):
    """Resume the game clock for a specific player"""
    try:
        if player not in ["white", "black"]:
            raise HTTPException(status_code=400, detail="Player must be 'white' or 'black'")
        
        success = clock_manager.start(game_id, player)
        if not success:
            raise HTTPException(status_code=404, detail="Clock not found for this game")
        
        return {"message": f"Clock resumed for {player} player"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games")
async def list_games():
    """List all active games"""
    try:
        games = []
        for game_id, game in game_manager.games.items():
            games.append({
                "id": game.id,
                "status": game.status.value,
                "white_player": game.white_player.username if game.white_player else None,
                "black_player": game.black_player.username if game.black_player else None,
                "created_at": game.created_at,
                "move_count": len(game.move_history)
            })
        
        return {"games": games}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/game/{game_id}")
async def delete_game(game_id: str):
    """Delete a game and clean up resources"""
    try:
        if game_id not in game_manager.games:
            raise HTTPException(status_code=404, detail="Game not found")
        
        # Clean up clock
        clock_manager.remove_clock(game_id)
        
        # Remove game
        del game_manager.games[game_id]
        if game_id in game_manager.chess_boards:
            del game_manager.chess_boards[game_id]
        if game_id in game_manager.move_stacks:
            del game_manager.move_stacks[game_id]
        if game_id in game_manager.redo_stacks:
            del game_manager.redo_stacks[game_id]
        
        return {"message": "Game deleted successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
