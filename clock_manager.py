import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from models import GameClock, TimeControl
import time


class ChessClock:
    def __init__(self):
        self.clocks: Dict[str, GameClock] = {}
        self.time_controls: Dict[str, TimeControl] = {}
        self.running_timers: Dict[str, asyncio.Task] = {}
        self.callbacks: Dict[str, Callable] = {}  # Callbacks for time updates and game over
    
    def create_clock(self, game_id: str, time_control: TimeControl) -> GameClock:
        """Create a new chess clock for a game"""
        clock = GameClock(
            white_time=float(time_control.initial_time),
            black_time=float(time_control.initial_time),
            active_player=None,
            last_move_time=None
        )
        
        self.clocks[game_id] = clock
        self.time_controls[game_id] = time_control
        
        return clock
    
    def start(self, game_id: str, player: str) -> bool:
        """Start the clock for a specific player"""
        if game_id not in self.clocks:
            return False
        
        clock = self.clocks[game_id]
        
        # Stop any existing timer
        self.pause(game_id)
        
        # Set active player and start time
        clock.active_player = player
        clock.last_move_time = datetime.utcnow()
        
        # Start the countdown timer
        self.running_timers[game_id] = asyncio.create_task(
            self._countdown_timer(game_id, player)
        )
        
        return True
    
    def pause(self, game_id: str) -> bool:
        """Pause the clock"""
        if game_id not in self.clocks:
            return False
        
        clock = self.clocks[game_id]
        
        # Update remaining time if clock was running
        if clock.active_player and clock.last_move_time:
            elapsed = (datetime.utcnow() - clock.last_move_time).total_seconds()
            
            if clock.active_player == "white":
                clock.white_time = max(0, clock.white_time - elapsed)
            else:
                clock.black_time = max(0, clock.black_time - elapsed)
        
        # Stop the timer task
        if game_id in self.running_timers:
            self.running_timers[game_id].cancel()
            del self.running_timers[game_id]
        
        clock.active_player = None
        clock.last_move_time = None
        
        return True
    
    def switch_turn(self, game_id: str) -> bool:
        """Switch the active player and add increment if applicable"""
        if game_id not in self.clocks:
            return False
        
        clock = self.clocks[game_id]
        time_control = self.time_controls.get(game_id)
        
        # Pause current player's clock and add increment
        if clock.active_player and clock.last_move_time:
            elapsed = (datetime.utcnow() - clock.last_move_time).total_seconds()
            
            if clock.active_player == "white":
                clock.white_time = max(0, clock.white_time - elapsed)
                if time_control and time_control.increment > 0:
                    clock.white_time += time_control.increment
            else:
                clock.black_time = max(0, clock.black_time - elapsed)
                if time_control and time_control.increment > 0:
                    clock.black_time += time_control.increment
        
        # Switch to the other player
        new_player = "black" if clock.active_player == "white" else "white"
        
        # Start the new player's clock
        return self.start(game_id, new_player)
    
    def get_remaining_time(self, game_id: str, player: str) -> Optional[float]:
        """Get remaining time for a specific player"""
        if game_id not in self.clocks:
            return None
        
        clock = self.clocks[game_id]
        
        # If this player is currently active, calculate current remaining time
        if clock.active_player == player and clock.last_move_time:
            elapsed = (datetime.utcnow() - clock.last_move_time).total_seconds()
            
            if player == "white":
                return max(0, clock.white_time - elapsed)
            else:
                return max(0, clock.black_time - elapsed)
        
        # Return stored time if player is not active
        return clock.white_time if player == "white" else clock.black_time
    
    def get_clock_state(self, game_id: str) -> Optional[GameClock]:
        """Get current clock state with updated times"""
        if game_id not in self.clocks:
            return None
        
        clock = self.clocks[game_id]
        
        # Create a copy with current times
        current_clock = GameClock(
            white_time=self.get_remaining_time(game_id, "white") or clock.white_time,
            black_time=self.get_remaining_time(game_id, "black") or clock.black_time,
            active_player=clock.active_player,
            last_move_time=clock.last_move_time
        )
        
        return current_clock
    
    def is_time_up(self, game_id: str, player: str) -> bool:
        """Check if a player's time has run out"""
        remaining_time = self.get_remaining_time(game_id, player)
        return remaining_time is not None and remaining_time <= 0
    
    def set_callback(self, game_id: str, callback: Callable):
        """Set a callback function for clock updates and time-up events"""
        self.callbacks[game_id] = callback
    
    def remove_clock(self, game_id: str):
        """Remove clock and cleanup resources"""
        self.pause(game_id)
        
        if game_id in self.clocks:
            del self.clocks[game_id]
        
        if game_id in self.time_controls:
            del self.time_controls[game_id]
        
        if game_id in self.callbacks:
            del self.callbacks[game_id]
    
    async def _countdown_timer(self, game_id: str, player: str):
        """Internal countdown timer that runs while a player's clock is active"""
        try:
            while True:
                await asyncio.sleep(1)  # Update every second
                
                if game_id not in self.clocks:
                    break
                
                remaining_time = self.get_remaining_time(game_id, player)
                
                if remaining_time is None:
                    break
                
                # Check if time is up
                if remaining_time <= 0:
                    # Time's up! Notify via callback
                    if game_id in self.callbacks:
                        await self._safe_callback(
                            self.callbacks[game_id], 
                            "time_up", 
                            {"game_id": game_id, "player": player}
                        )
                    break
                
                # Send periodic time updates (every 10 seconds when > 60s, every second when < 60s)
                should_update = (
                    remaining_time <= 60 or  # Update every second in last minute
                    int(remaining_time) % 10 == 0  # Update every 10 seconds otherwise
                )
                
                if should_update and game_id in self.callbacks:
                    await self._safe_callback(
                        self.callbacks[game_id],
                        "clock_update",
                        {
                            "game_id": game_id,
                            "white_time": self.get_remaining_time(game_id, "white"),
                            "black_time": self.get_remaining_time(game_id, "black"),
                            "active_player": player
                        }
                    )
        
        except asyncio.CancelledError:
            # Timer was cancelled (normal when switching turns or pausing)
            pass
        except Exception as e:
            # Log error but don't crash
            print(f"Error in countdown timer for game {game_id}: {e}")
    
    async def _safe_callback(self, callback: Callable, event_type: str, data: dict):
        """Safely execute callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event_type, data)
            else:
                callback(event_type, data)
        except Exception as e:
            print(f"Error in clock callback: {e}")
    
    def get_formatted_time(self, seconds: float) -> str:
        """Format time in MM:SS or HH:MM:SS format"""
        if seconds < 0:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


# Global clock manager instance
clock_manager = ChessClock()
