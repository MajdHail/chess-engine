"""Play Majd Chess against Stockfish, swapping colours each game.

    python match.py --games 2 --time 1 --elo 1500

Leave out --elo for full-strength Stockfish. Games are appended to match.pgn.
"""
import argparse
import sys
from pathlib import Path

import chess
import chess.engine
import chess.pgn

HERE = Path(__file__).parent
STOCKFISH = str(Path.home() / "Applications/stockfish")
MAJD = "MajdChess"


def play_game(engines, white, black, limit):
    board = chess.Board()
    while not board.is_game_over(claim_draw=True):
        name = white if board.turn == chess.WHITE else black
        move = engines[name].play(board, limit, game=board.root()).move
        prefix = f"{board.fullmove_number}." if board.turn == chess.WHITE else f"{board.fullmove_number}..."
        print(f"{prefix} {board.san(move)}  ({name})", flush=True)
        board.push(move)
    return board


def main():
    parser = argparse.ArgumentParser(description="Play Majd Chess against Stockfish.")
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--time", type=float, default=1.0, help="seconds per move")
    parser.add_argument("--elo", type=int, help="limit Stockfish to this rating (1320-3190)")
    args = parser.parse_args()

    stockfish_name = f"Stockfish ({args.elo})" if args.elo else "Stockfish"
    majd = chess.engine.SimpleEngine.popen_uci([sys.executable, str(HERE / "uci.py")])
    stockfish = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    if args.elo:
        stockfish.configure({"UCI_LimitStrength": True, "UCI_Elo": args.elo})
    engines = {MAJD: majd, stockfish_name: stockfish}

    wins = draws = losses = 0
    try:
        for number in range(args.games):
            white, black = (MAJD, stockfish_name) if number % 2 == 0 else (stockfish_name, MAJD)
            print(f"\nGame {number + 1}: {white} (white) vs {black} (black)")
            board = play_game(engines, white, black, chess.engine.Limit(time=args.time))

            winner = board.outcome(claim_draw=True).winner
            if winner is None:
                draws += 1
            elif (winner == chess.WHITE) == (white == MAJD):
                wins += 1
            else:
                losses += 1
            print(f"Result: {board.result(claim_draw=True)} ({board.outcome(claim_draw=True).termination.name.lower()})")

            game = chess.pgn.Game.from_board(board)
            game.headers.update(White=white, Black=black, Event="Majd Chess vs Stockfish")
            game.headers["Result"] = board.result(claim_draw=True)
            with open(HERE / "match.pgn", "a") as pgn:
                print(game, end="\n\n", file=pgn)
    finally:
        majd.quit()
        stockfish.quit()

    print(f"\nMajd Chess: {wins} wins, {draws} draws, {losses} losses against {stockfish_name}")


if __name__ == "__main__":
    main()
