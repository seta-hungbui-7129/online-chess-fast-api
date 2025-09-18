from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from api import router as api_router, game_manager
from websocket_handler import WebSocketHandler
from clock_manager import clock_manager


# Global WebSocket handler
websocket_handler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global websocket_handler
    
    # Startup
    print("Starting Chess Server...")
    websocket_handler = WebSocketHandler(game_manager)
    print("Chess Server started successfully!")
    
    yield
    
    # Shutdown
    print("Shutting down Chess Server...")
    # Clean up any running timers
    for game_id in list(clock_manager.running_timers.keys()):
        clock_manager.remove_clock(game_id)
    print("Chess Server shutdown complete!")


# Create FastAPI application
app = FastAPI(
    title="Chess Server API",
    description="A real-time chess server with WebSocket support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["Chess Game API"])


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Chess Server API",
        "version": "1.0.0",
        "docs": "/docs",
        "websocket": "/ws/game/{game_id}?player_id={player_id}",
        "endpoints": {
            "create_game": "POST /api/v1/game",
            "get_game": "GET /api/v1/game/{game_id}",
            "make_move": "POST /api/v1/game/{game_id}/move",
            "undo_move": "POST /api/v1/game/{game_id}/undo",
            "redo_move": "POST /api/v1/game/{game_id}/redo",
            "join_game": "POST /api/v1/game/{game_id}/join",
            "get_pgn": "GET /api/v1/game/{game_id}/pgn",
            "get_clock": "GET /api/v1/game/{game_id}/clock",
            "list_games": "GET /api/v1/games"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_games": len(game_manager.games),
        "active_clocks": len(clock_manager.clocks)
    }


@app.websocket("/ws/game/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    """WebSocket endpoint for real-time game communication"""
    global websocket_handler
    
    if websocket_handler is None:
        await websocket.close(code=1011, reason="Server not ready")
        return
    
    # Validate game exists
    try:
        game_manager.get_game_state(game_id)
    except ValueError:
        await websocket.close(code=1008, reason="Game not found")
        return
    
    # Handle WebSocket connection
    await websocket_handler.handle_websocket(websocket, game_id, player_id)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Not found", "detail": str(exc)}


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"error": "Internal server error", "detail": "An unexpected error occurred"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
        log_level="info"
    )
