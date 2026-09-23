"""Play against the engine in the terminal: python play.py --level 5 --color white"""
import argparse

import chess

from engine import Engine

HELP = """Enter moves in SAN (Nf3, exd5, O-O) or UCI (g1f3).
Commands: level N (1-10), hint, undo, flip, quit"""


def main():
    parser = argparse.ArgumentParser(description="Play chess against the engine.")
    parser.add_argument("--level", type=int, default=5, choices=range(1, 11), metavar="1-10",
                        help="difficulty, 1 is a beginner and 10 is the strongest (default 5)")
    parser.add_argument("--color", choices=["white", "black"], default="white")
    args = parser.parse_args()

    engine = Engine(args.level)
    board = chess.Board()
    human = chess.WHITE if args.color == "white" else chess.BLACK
    print(HELP)

    while not board.is_game_over():
        if board.turn != human:
            move = engine.search(board)
            print(f"\nEngine (level {engine.level}) plays {board.san(move)}")
            board.push(move)
            continue

        print("\n" + board.unicode(orientation=human, empty_square="."))
        try:
            text = input(f"\nYour move (level {engine.level}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if text == "quit":
            return
        if text == "undo":
            if len(board.move_stack) >= 2:
                board.pop()
                board.pop()
            continue
        if text == "hint":
            print("Hint:", board.san(engine.search(board)))
            continue
        if text == "flip":
            human = not human
            continue
        if text.startswith("level"):
            try:
                engine.set_level(int(text.split()[1]))
                print(f"Difficulty set to {engine.level}")
            except (IndexError, ValueError):
                print("Usage: level N  (1-10)")
            continue

        try:
            board.push_san(text)
        except ValueError:
            try:
                board.push_uci(text)
            except ValueError:
                print("Illegal or unrecognized move. " + HELP)

    print("\n" + board.unicode(orientation=human, empty_square="."))
    print(f"\nGame over: {board.result()} ({board.outcome().termination.name.lower().replace('_', ' ')})")


if __name__ == "__main__":
    main()
