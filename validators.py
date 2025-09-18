"""Validation utilities for the chess server"""

import re
from typing import Optional
import chess
from exceptions import ValidationException, InvalidMoveException


class ChessValidator:
    """Validator for chess-related inputs"""
    
    SQUARE_PATTERN = re.compile(r'^[a-h][1-8]$')
    PROMOTION_PIECES = {'q', 'r', 'b', 'n'}
    
    @staticmethod
    def validate_square(square: str, field_name: str = "square") -> str:
        """Validate chess square notation (e.g., 'e4')"""
        if not square:
            raise ValidationException(f"{field_name} cannot be empty", field_name)
        
        if not isinstance(square, str):
            raise ValidationException(f"{field_name} must be a string", field_name)
        
        square = square.lower().strip()
        
        if not ChessValidator.SQUARE_PATTERN.match(square):
            raise ValidationException(
                f"Invalid {field_name} format. Expected format: [a-h][1-8] (e.g., 'e4')",
                field_name
            )
        
        return square
    
    @staticmethod
    def validate_promotion(promotion: Optional[str]) -> Optional[str]:
        """Validate promotion piece"""
        if promotion is None:
            return None
        
        if not isinstance(promotion, str):
            raise ValidationException("Promotion must be a string", "promotion")
        
        promotion = promotion.lower().strip()
        
        if promotion not in ChessValidator.PROMOTION_PIECES:
            raise ValidationException(
                f"Invalid promotion piece. Must be one of: {', '.join(ChessValidator.PROMOTION_PIECES)}",
                "promotion"
            )
        
        return promotion
    
    @staticmethod
    def validate_move_format(from_square: str, to_square: str, promotion: Optional[str] = None):
        """Validate move format"""
        from_sq = ChessValidator.validate_square(from_square, "from_square")
        to_sq = ChessValidator.validate_square(to_square, "to_square")
        promo = ChessValidator.validate_promotion(promotion)
        
        if from_sq == to_sq:
            raise InvalidMoveException("From and to squares cannot be the same", from_sq, to_sq)
        
        return from_sq, to_sq, promo
    
    @staticmethod
    def validate_chess_move(board: chess.Board, from_square: str, to_square: str, 
                          promotion: Optional[str] = None) -> chess.Move:
        """Validate that a move is legal on the given board"""
        try:
            from_sq = chess.parse_square(from_square)
            to_sq = chess.parse_square(to_square)
        except ValueError as e:
            raise InvalidMoveException(f"Invalid square notation: {e}", from_square, to_square)
        
        # Create move object
        move = chess.Move(from_sq, to_sq)
        
        # Handle promotion
        if promotion:
            promotion_piece = {
                'q': chess.QUEEN,
                'r': chess.ROOK,
                'b': chess.BISHOP,
                'n': chess.KNIGHT
            }.get(promotion.lower())
            
            if promotion_piece:
                move.promotion = promotion_piece
        
        # Check if move is legal
        if move not in board.legal_moves:
            # Try to provide more specific error message
            piece = board.piece_at(from_sq)
            if piece is None:
                raise InvalidMoveException(
                    f"No piece at {from_square}",
                    from_square, to_square
                )
            
            # Check if it's the right player's turn
            if piece.color != board.turn:
                player_turn = "white" if board.turn else "black"
                piece_color = "white" if piece.color else "black"
                raise InvalidMoveException(
                    f"It's {player_turn}'s turn, but you're trying to move a {piece_color} piece",
                    from_square, to_square
                )
            
            # Generic illegal move message
            raise InvalidMoveException(
                f"Illegal move: {from_square} to {to_square}",
                from_square, to_square
            )
        
        return move


class PlayerValidator:
    """Validator for player-related inputs"""
    
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{3,20}$')
    
    @staticmethod
    def validate_username(username: str) -> str:
        """Validate player username"""
        if not username:
            raise ValidationException("Username cannot be empty", "username")
        
        if not isinstance(username, str):
            raise ValidationException("Username must be a string", "username")
        
        username = username.strip()
        
        if not PlayerValidator.USERNAME_PATTERN.match(username):
            raise ValidationException(
                "Username must be 3-20 characters long and contain only letters, numbers, hyphens, and underscores",
                "username"
            )
        
        return username
    
    @staticmethod
    def validate_rating(rating: int) -> int:
        """Validate player rating"""
        if not isinstance(rating, int):
            raise ValidationException("Rating must be an integer", "rating")
        
        if rating < 0 or rating > 3000:
            raise ValidationException("Rating must be between 0 and 3000", "rating")
        
        return rating
    
    @staticmethod
    def validate_player_turn(game, player_id: str, current_turn: str):
        """Validate that it's the player's turn"""
        if current_turn == "white":
            if not game.white_player or game.white_player.id != player_id:
                raise InvalidMoveException("Not your turn - it's white's turn")
        else:
            if not game.black_player or game.black_player.id != player_id:
                raise InvalidMoveException("Not your turn - it's black's turn")


class GameValidator:
    """Validator for game-related inputs"""
    
    @staticmethod
    def validate_game_id(game_id: str) -> str:
        """Validate game ID format"""
        if not game_id:
            raise ValidationException("Game ID cannot be empty", "game_id")
        
        if not isinstance(game_id, str):
            raise ValidationException("Game ID must be a string", "game_id")
        
        game_id = game_id.strip()
        
        # Basic UUID format validation (loose)
        if len(game_id) < 10:
            raise ValidationException("Invalid game ID format", "game_id")
        
        return game_id
    
    @staticmethod
    def validate_time_control(initial_time: int, increment: int = 0):
        """Validate time control settings"""
        if not isinstance(initial_time, int):
            raise ValidationException("Initial time must be an integer", "initial_time")
        
        if not isinstance(increment, int):
            raise ValidationException("Increment must be an integer", "increment")
        
        if initial_time <= 0:
            raise ValidationException("Initial time must be positive", "initial_time")
        
        if increment < 0:
            raise ValidationException("Increment cannot be negative", "increment")
        
        # Reasonable limits
        if initial_time > 7200:  # 2 hours
            raise ValidationException("Initial time cannot exceed 2 hours", "initial_time")
        
        if increment > 60:  # 1 minute
            raise ValidationException("Increment cannot exceed 1 minute", "increment")
        
        return initial_time, increment


class WebSocketValidator:
    """Validator for WebSocket messages"""
    
    VALID_EVENTS = {
        'join', 'move', 'undo', 'redo', 'get_state', 'ping'
    }
    
    @staticmethod
    def validate_message_format(message_data: dict):
        """Validate WebSocket message format"""
        if not isinstance(message_data, dict):
            raise ValidationException("Message must be a JSON object")
        
        if 'event' not in message_data:
            raise ValidationException("Message must contain 'event' field", "event")
        
        event = message_data['event']
        if not isinstance(event, str):
            raise ValidationException("Event must be a string", "event")
        
        if event not in WebSocketValidator.VALID_EVENTS:
            raise ValidationException(
                f"Invalid event type. Valid events: {', '.join(WebSocketValidator.VALID_EVENTS)}",
                "event"
            )
        
        # Validate data field exists and is dict
        if 'data' not in message_data:
            message_data['data'] = {}
        
        if not isinstance(message_data['data'], dict):
            raise ValidationException("Data field must be an object", "data")
        
        return message_data
    
    @staticmethod
    def validate_move_event_data(data: dict):
        """Validate move event data"""
        if 'from' not in data:
            raise ValidationException("Move event must contain 'from' field", "from")
        
        if 'to' not in data:
            raise ValidationException("Move event must contain 'to' field", "to")
        
        from_square = ChessValidator.validate_square(data['from'], "from")
        to_square = ChessValidator.validate_square(data['to'], "to")
        promotion = ChessValidator.validate_promotion(data.get('promotion'))
        
        return from_square, to_square, promotion
