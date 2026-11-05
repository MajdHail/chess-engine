"""Play Majd Chess against Stockfish, swapping colors each game.

    python match.py --stockfish /path/to/stockfish --games 10 --time 1 --elo 1800

Leave out --elo for full-strength Stockfish. Finished games are appended to match.pgn.
"""

import argparse
import shutil
import sys
from pathlib import Path

import chess
import chess.engine
import chess.pgn

HERE = Path(__file__).parent
MAJD = "MajdChess"


def play_game(engines, white, black, limit):
    """Play one game and return the final board, printing each move as it happens."""
    board = chess.Board()
    while not board.is_game_over(claim_draw=True):
        name = white if board.turn == chess.WHITE else black
        move = engines[name].play(board, limit, game=board.root()).move
        dots = "." if board.turn == chess.WHITE else "..."
        print(f"{board.fullmove_number}{dots} {board.san(move)}  ({name})", flush=True)
        board.push(move)
    return board


def save_game(board, white, black):
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        Event="Majd Chess vs Stockfish",
        White=white,
        Black=black,
        Result=board.result(claim_draw=True),
    )
    with open(HERE / "match.pgn", "a") as pgn:
        print(game, end="\n\n", file=pgn)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stockfish", default=shutil.which("stockfish"), help="path to Stockfish")
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--time", type=float, default=1.0, help="seconds per move")
    parser.add_argument("--elo", type=int, help="limit Stockfish to this rating (1320-3190)")
    args = parser.parse_args()
    if not args.stockfish:
        parser.error("Stockfish was not found on your PATH, so pass --stockfish /path/to/stockfish")

    stockfish_name = f"Stockfish ({args.elo})" if args.elo else "Stockfish"
    majd = chess.engine.SimpleEngine.popen_uci([sys.executable, str(HERE / "uci.py")])
    stockfish = chess.engine.SimpleEngine.popen_uci(args.stockfish)
    if args.elo:
        stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": args.elo})
    engines = {MAJD: majd, stockfish_name: stockfish}
    limit = chess.engine.Limit(time=args.time)

    wins = draws = losses = 0
    try:
        for number in range(args.games):
            majd_is_white = number % 2 == 0
            white, black = (MAJD, stockfish_name) if majd_is_white else (stockfish_name, MAJD)
            print(f"\nGame {number + 1}: {white} (white) vs {black} (black)")
            board = play_game(engines, white, black, limit)

            outcome = board.outcome(claim_draw=True)
            if outcome.winner is None:
                draws += 1
            elif outcome.winner == majd_is_white:
                wins += 1
            else:
                losses += 1
            print(f"Result: {outcome.result()} ({outcome.termination.name.lower()})")
            save_game(board, white, black)
    finally:
        majd.quit()
        stockfish.quit()

    print(f"\nMajd Chess: {wins} wins, {draws} draws, {losses} losses against {stockfish_name}")


if __name__ == "__main__":
    main()
