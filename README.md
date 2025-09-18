# Full-Stack Online Chess Application

This project is a complete, real-time online chess application built with a FastAPI backend 

## Project Overview

- **Backend (FastAPI)**: A powerful and asynchronous Python server that manages game logic, real-time communication, and provides a REST API for game management.


## Backend: Chess Server (FastAPI)

The backend is a robust chess server that handles all game logic, from move validation to real-time updates.

### Features

- ✅ **Rule Enforcement**: Utilizes the `python-chess` library for legal move validation, check, checkmate, and stalemate detection.
- ✅ **Game State Tracking**: Manages game state with FEN (Forsyth-Edwards Notation) for board positions and PGN (Portable Game Notation) for move history.
- ✅ **Real-Time Communication**: Uses WebSockets to broadcast moves, clock updates, and game events to all connected players instantly.
- ✅ **Chess Clock**: Implements per-player countdown timers with optional time increments.
- ✅ **REST API**: Provides a comprehensive set of endpoints for creating, joining, and managing games.
- ✅ **Error Handling**: Includes detailed input validation and custom exceptions for robust operation.

### How to Run the Backend

1.  **Navigate to the backend directory**:

    ```bash
    cd online-chess-fast-api
    ```

2.  **Install dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the server**:
    ```bash
    python3 main.py
    ```
    The server will start on `http://localhost:8081`.

### How to Test the API

You can test the API using the interactive documentation or with a command-line tool like `curl`.

#### 1. Using Interactive API Docs

Once the server is running, open your browser and navigate to:

- **http://localhost:8081/docs**

This page provides an interactive interface where you can test each endpoint directly from your browser.

#### 2. Using `curl`

Here are some examples of how to test the API with `curl`.

**A. Create a New Game**

This command creates a new game with two players and a 10-minute clock with a 5-second increment.

```bash
curl -X POST "http://localhost:8081/api/v1/game" \
  -H "Content-Type: application/json" \
  -d '{
    "white_player": {"username": "Alice", "rating": 1500},
    "black_player": {"username": "Bob", "rating": 1450},
    "time_control": {"initial_time": 600, "increment": 5}
  }'
```

**B. Get the Game State**

Replace `{game_id}` with the ID from the previous step.

```bash
curl http://localhost:8081/api/v1/game/{game_id}
```

**C. Make a Move**

This command makes the move `e2` to `e4`.

```bash
curl -X POST "http://localhost:8081/api/v1/game/{game_id}/move" \
  -H "Content-Type: application/json" \
  -d '{
    "from_square": "e2",
    "to_square": "e4"
  }'
```

**D. List All Games**

```bash
curl http://localhost:8081/api/v1/games
```

### Backend Test Suite

To run the automated test suite for the backend:

```bash
python3 test_chess_server.py
```
