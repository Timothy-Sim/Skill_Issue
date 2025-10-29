import requests
import chess
import chess.pgn
import chess.engine
from io import StringIO
import os
CHESS_COM_API_URL = "https://api.chess.com/pub/player"
YOUR_USER_AGENT = "Skill Issue Prototype"

def get_player_matches(username, year, month):
    url = f"{CHESS_COM_API_URL}/{username}/games/{year:04d}/{month:02d}"
    headers = {"User-Agent": YOUR_USER_AGENT}
    print(f"Requesting URL: {url}")
    response = requests.get(url, headers=headers)
    try:
        response = requests.get(url, headers=headers)
        # This will raise an error for bad status codes (like 404, 500)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching games for {username}: {e}")
        return None

"""
    Parses a single PGN string into a chess.Game object.
    Returns the game object or None on failure.
    """
def pgn_parse(pgn_file):
    # to access all information about the game such as elo, time, etc, use
    # headers = dict(game.headers)
    if not pgn_file:
        return None
        
    try:
        pgn_io = StringIO(pgn_file)
        game = chess.pgn.read_game(pgn_io)
        return game
    except Exception as e:
        # PGNs can sometimes be malformed
        print(f"Error parsing PGN: {e}")
        return None


def fen_notation(game):
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
        print(board.fen())

def stockfish(game):
    engine_path = r"stockfish\stockfish-windows-x86-64-avx2.exe"  # relative path
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)

    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
        
        # Get Stockfish evaluation for this position
        info = engine.analyse(board, chess.engine.Limit(depth=15))
        print(board.fen(), info["score"])

    engine.quit()

if __name__ == "__main__":
    username = "simothy03"
    year = 2023
    month = 1

    games_data = get_player_matches(username, year, month)

    if games_data:
        # Print the PGN of the first game in the archive
        if games_data.get("games"):
            first_game_pgn = games_data["games"][0].get("pgn")
            print(first_game_pgn)

            stockfish(pgn_parse(first_game_pgn))