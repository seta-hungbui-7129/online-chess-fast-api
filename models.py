from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class GameStatus(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"
    ABANDONED = "abandoned"


class GameResult(str, Enum):
    WHITE_WINS = "white_wins"
    BLACK_WINS = "black_wins"
    DRAW = "draw"
    STALEMATE = "stalemate"
    ONGOING = "ongoing"


class Player(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    rating: int = Field(default=1200, ge=0, le=3000)
    
    class Config:
        json_encoders = {
            uuid.UUID: str
        }


class Move(BaseModel):
    from_square: str = Field(..., description="Source square in algebraic notation (e.g., 'e2')")
    to_square: str = Field(..., description="Target square in algebraic notation (e.g., 'e4')")
    promotion: Optional[str] = Field(None, description="Promotion piece (q, r, b, n)")
    fen_after_move: str = Field(..., description="FEN string after the move")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    move_number: int = Field(..., description="Move number in the game")
    san_notation: str = Field(..., description="Standard Algebraic Notation of the move")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TimeControl(BaseModel):
    initial_time: int = Field(..., description="Initial time in seconds")
    increment: int = Field(default=0, description="Increment per move in seconds")


class GameClock(BaseModel):
    white_time: float = Field(..., description="Remaining time for white player in seconds")
    black_time: float = Field(..., description="Remaining time for black player in seconds")
    last_move_time: Optional[datetime] = Field(None, description="Timestamp of last move")
    active_player: Optional[str] = Field(None, description="Currently active player ('white' or 'black')")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Game(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    white_player: Optional[Player] = None
    black_player: Optional[Player] = None
    current_fen: str = Field(default="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    pgn_history: List[str] = Field(default_factory=list)
    move_history: List[Move] = Field(default_factory=list)
    clock: Optional[GameClock] = None
    time_control: Optional[TimeControl] = None
    status: GameStatus = GameStatus.WAITING
    result: GameResult = GameResult.ONGOING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    current_turn: str = Field(default="white", description="Current player's turn ('white' or 'black')")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: str
        }


class WebSocketMessage(BaseModel):
    event: str = Field(..., description="Event type (join, move, undo, redo, clock_update, game_over)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    game_id: Optional[str] = Field(None, description="Game ID for the event")
    player_id: Optional[str] = Field(None, description="Player ID who sent the event")


class MoveRequest(BaseModel):
    from_square: str = Field(..., description="Source square (e.g., 'e2')")
    to_square: str = Field(..., description="Target square (e.g., 'e4')")
    promotion: Optional[str] = Field(None, description="Promotion piece (q, r, b, n)")


class CreateGameRequest(BaseModel):
    white_player: Player
    black_player: Optional[Player] = None
    time_control: Optional[TimeControl] = None


class GameStateResponse(BaseModel):
    game: Game
    legal_moves: List[str] = Field(default_factory=list)
    is_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False
    is_draw: bool = False
