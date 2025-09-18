import chess
import chess.pgn
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from models import Game, Player, Move, GameStatus, GameResult, TimeControl, GameClock
from exceptions import GameNotFoundException, InvalidMoveException, GameStateException
from validators import ChessValidator, GameValidator
import uuid


class GameManager:
    def __init__(self):
        self.games: Dict[str, Game] = {}
        self.chess_boards: Dict[str, chess.Board] = {}
        self.move_stacks: Dict[str, List[chess.Move]] = {}  # For undo/redo functionality
        self.redo_stacks: Dict[str, List[chess.Move]] = {}
    
    def create_game(self, white_player: Player, black_player: Optional[Player] = None, 
                   time_control: Optional[TimeControl] = None) -> Game:
        """Create a new chess game"""
        game_id = str(uuid.uuid4())
        
        # Initialize game clock if time control is provided
        game_clock = None
        if time_control:
            game_clock = GameClock(
                white_time=float(time_control.initial_time),
                black_time=float(time_control.initial_time),
                active_player="white"
            )
        
        game = Game(
            id=game_id,
            white_player=white_player,
            black_player=black_player,
            time_control=time_control,
            clock=game_clock,
            status=GameStatus.WAITING if black_player is None else GameStatus.ACTIVE
        )
        
        # Initialize chess board
        board = chess.Board()
        
        # Store game and board
        self.games[game_id] = game
        self.chess_boards[game_id] = board
        self.move_stacks[game_id] = []
        self.redo_stacks[game_id] = []
        
        return game
    
    def join_game(self, game_id: str, player: Player) -> Game:
        """Add a second player to a waiting game"""
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")
        
        game = self.games[game_id]
        if game.status != GameStatus.WAITING:
            raise ValueError("Game is not waiting for players")
        
        if game.black_player is None:
            game.black_player = player
            game.status = GameStatus.ACTIVE
            game.updated_at = datetime.utcnow()
        else:
            raise ValueError("Game is already full")
        
        return game
    
    def make_move(self, game_id: str, from_square: str, to_square: str,
                  promotion: Optional[str] = None) -> Tuple[Game, Move]:
        """Make a move in the game"""
        # Validate inputs
        game_id = GameValidator.validate_game_id(game_id)
        from_square, to_square, promotion = ChessValidator.validate_move_format(
            from_square, to_square, promotion
        )

        if game_id not in self.games:
            raise GameNotFoundException(game_id)

        game = self.games[game_id]
        board = self.chess_boards[game_id]

        if game.status != GameStatus.ACTIVE:
            raise GameStateException(
                f"Game is not active (current status: {game.status.value})",
                game.status.value
            )

        # Validate and create chess move
        move = ChessValidator.validate_chess_move(board, from_square, to_square, promotion)
        
        # Get SAN notation before making the move
        san_notation = board.san(move)

        # Make the move
        board.push(move)
        self.move_stacks[game_id].append(move)
        self.redo_stacks[game_id].clear()  # Clear redo stack when new move is made

        # Update game state
        game.current_fen = board.fen()
        game.current_turn = "black" if board.turn == chess.BLACK else "white"
        game.updated_at = datetime.utcnow()

        # Create move record
        move_record = Move(
            from_square=from_square,
            to_square=to_square,
            promotion=promotion,
            fen_after_move=board.fen(),
            move_number=len(game.move_history) + 1,
            san_notation=san_notation
        )
        
        game.move_history.append(move_record)
        game.pgn_history.append(san_notation)
        
        # Check game end conditions
        self._check_game_end(game_id)
        
        return game, move_record
    
    def undo_move(self, game_id: str) -> Game:
        """Undo the last move"""
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")
        
        game = self.games[game_id]
        board = self.chess_boards[game_id]
        move_stack = self.move_stacks[game_id]
        
        if not move_stack:
            raise ValueError("No moves to undo")
        
        # Undo the move
        last_move = board.pop()
        undone_move = move_stack.pop()
        self.redo_stacks[game_id].append(undone_move)
        
        # Update game state
        game.current_fen = board.fen()
        game.current_turn = "black" if board.turn == chess.BLACK else "white"
        game.updated_at = datetime.utcnow()
        
        # Remove from history
        if game.move_history:
            game.move_history.pop()
        if game.pgn_history:
            game.pgn_history.pop()
        
        # Reset game status if it was finished
        if game.status == GameStatus.FINISHED:
            game.status = GameStatus.ACTIVE
            game.result = GameResult.ONGOING
        
        return game
    
    def redo_move(self, game_id: str) -> Game:
        """Redo a previously undone move"""
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")
        
        game = self.games[game_id]
        board = self.chess_boards[game_id]
        redo_stack = self.redo_stacks[game_id]
        
        if not redo_stack:
            raise ValueError("No moves to redo")
        
        # Get SAN notation before making the move
        move_to_redo = redo_stack.pop()
        san_notation = board.san(move_to_redo)

        # Redo the move
        board.push(move_to_redo)
        self.move_stacks[game_id].append(move_to_redo)

        # Update game state
        game.current_fen = board.fen()
        game.current_turn = "black" if board.turn == chess.BLACK else "white"
        game.updated_at = datetime.utcnow()

        # Recreate move record
        move_record = Move(
            from_square=chess.square_name(move_to_redo.from_square),
            to_square=chess.square_name(move_to_redo.to_square),
            promotion=chess.piece_name(move_to_redo.promotion).lower() if move_to_redo.promotion else None,
            fen_after_move=board.fen(),
            move_number=len(game.move_history) + 1,
            san_notation=san_notation
        )
        
        game.move_history.append(move_record)
        game.pgn_history.append(san_notation)
        
        # Check game end conditions
        self._check_game_end(game_id)
        
        return game
    
    def get_game_state(self, game_id: str) -> Game:
        """Get current game state"""
        game_id = GameValidator.validate_game_id(game_id)
        if game_id not in self.games:
            raise GameNotFoundException(game_id)
        return self.games[game_id]
    
    def get_legal_moves(self, game_id: str) -> List[str]:
        """Get all legal moves for current position"""
        if game_id not in self.chess_boards:
            raise ValueError(f"Game {game_id} not found")
        
        board = self.chess_boards[game_id]
        return [move.uci() for move in board.legal_moves]
    
    def is_checkmate(self, game_id: str) -> bool:
        """Check if current position is checkmate"""
        if game_id not in self.chess_boards:
            return False
        return self.chess_boards[game_id].is_checkmate()
    
    def is_stalemate(self, game_id: str) -> bool:
        """Check if current position is stalemate"""
        if game_id not in self.chess_boards:
            return False
        return self.chess_boards[game_id].is_stalemate()
    
    def is_check(self, game_id: str) -> bool:
        """Check if current position is check"""
        if game_id not in self.chess_boards:
            return False
        return self.chess_boards[game_id].is_check()
    
    def is_draw(self, game_id: str) -> bool:
        """Check if current position is a draw"""
        if game_id not in self.chess_boards:
            return False
        board = self.chess_boards[game_id]
        return (board.is_stalemate() or 
                board.is_insufficient_material() or 
                board.is_seventyfive_moves() or 
                board.is_fivefold_repetition())
    
    def _check_game_end(self, game_id: str):
        """Check and update game end conditions"""
        game = self.games[game_id]
        board = self.chess_boards[game_id]
        
        if board.is_checkmate():
            game.status = GameStatus.FINISHED
            game.result = GameResult.WHITE_WINS if board.turn == chess.BLACK else GameResult.BLACK_WINS
        elif board.is_stalemate():
            game.status = GameStatus.FINISHED
            game.result = GameResult.STALEMATE
        elif self.is_draw(game_id):
            game.status = GameStatus.FINISHED
            game.result = GameResult.DRAW
    
    def get_pgn(self, game_id: str) -> str:
        """Get PGN representation of the game"""
        if game_id not in self.games:
            raise ValueError(f"Game {game_id} not found")
        
        game = self.games[game_id]
        board = self.chess_boards[game_id]
        
        # Create PGN game
        pgn_game = chess.pgn.Game()
        
        # Set headers
        pgn_game.headers["White"] = game.white_player.username if game.white_player else "Unknown"
        pgn_game.headers["Black"] = game.black_player.username if game.black_player else "Unknown"
        pgn_game.headers["Date"] = game.created_at.strftime("%Y.%m.%d")
        pgn_game.headers["Result"] = self._get_pgn_result(game.result)
        
        # Add moves
        node = pgn_game
        temp_board = chess.Board()
        for move in self.move_stacks[game_id]:
            node = node.add_variation(move)
            temp_board.push(move)
        
        return str(pgn_game)
    
    def _get_pgn_result(self, result: GameResult) -> str:
        """Convert GameResult to PGN result format"""
        result_map = {
            GameResult.WHITE_WINS: "1-0",
            GameResult.BLACK_WINS: "0-1",
            GameResult.DRAW: "1/2-1/2",
            GameResult.STALEMATE: "1/2-1/2",
            GameResult.ONGOING: "*"
        }
        return result_map.get(result, "*")
