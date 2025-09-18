"""Custom exceptions for the chess server"""

class ChessServerException(Exception):
    """Base exception for chess server errors"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class GameNotFoundException(ChessServerException):
    """Raised when a game is not found"""
    def __init__(self, game_id: str):
        super().__init__(f"Game {game_id} not found", "GAME_NOT_FOUND")
        self.game_id = game_id


class InvalidMoveException(ChessServerException):
    """Raised when an invalid move is attempted"""
    def __init__(self, message: str, from_square: str = None, to_square: str = None):
        super().__init__(message, "INVALID_MOVE")
        self.from_square = from_square
        self.to_square = to_square


class GameStateException(ChessServerException):
    """Raised when game is in invalid state for operation"""
    def __init__(self, message: str, current_state: str = None):
        super().__init__(message, "INVALID_GAME_STATE")
        self.current_state = current_state


class PlayerException(ChessServerException):
    """Raised for player-related errors"""
    def __init__(self, message: str, player_id: str = None):
        super().__init__(message, "PLAYER_ERROR")
        self.player_id = player_id


class ClockException(ChessServerException):
    """Raised for clock-related errors"""
    def __init__(self, message: str, game_id: str = None):
        super().__init__(message, "CLOCK_ERROR")
        self.game_id = game_id


class ValidationException(ChessServerException):
    """Raised for input validation errors"""
    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field
