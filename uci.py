"""UCI mode: lets other chess programs use this engine.

UCI (Universal Chess Interface) is the standard text protocol chess engines
speak. A chess GUI like Cute Chess or Arena starts `python uci.py`, writes
commands to it, and reads replies. For example:

    GUI sends:     position startpos moves e2e4
    GUI sends:     go movetime 1000
    engine sends:  info depth 5 score cp -20 ...
    engine sends:  bestmove e7e5

This means you can make the engine play against other engines, or against
itself, without the desktop app.
"""
import sys

import chess

from engine import MATE, MATE_THRESHOLD, Engine


def parse_position(tokens):
    """Handle 'position startpos moves ...' or 'position fen <fen> moves ...'."""
    moves = []
    if "moves" in tokens:
        i = tokens.index("moves")
        tokens, moves = tokens[:i], tokens[i + 1:]
    board = chess.Board() if tokens[1] == "startpos" else chess.Board(" ".join(tokens[2:]))
    for move in moves:
        board.push_uci(move)
    return board


def parse_go(tokens, board, engine):
    """Return (time_limit, max_depth). The difficulty level stays an upper bound on both."""
    args = dict(zip(tokens[1::2], tokens[2::2]))
    if "depth" in args:
        return engine.time_limit, min(int(args["depth"]), engine.max_depth)
    if "movetime" in args:
        return int(args["movetime"]) / 1000, None
    side = "w" if board.turn == chess.WHITE else "b"
    if f"{side}time" in args:
        remaining = int(args[f"{side}time"]) / 1000
        increment = int(args.get(f"{side}inc", 0)) / 1000
        # Spend about 1/30 of the clock per move, plus half the increment.
        return min(engine.time_limit, remaining / 30 + increment / 2), None
    # "go infinite" runs as a normal timed search, because nothing listens for "stop" mid-search.
    return None, None


def format_score(score):
    """UCI wants 'cp 35' for normal scores and 'mate 3' for forced mates."""
    if abs(score) >= MATE_THRESHOLD:
        moves = (MATE - abs(score) + 1) // 2
        return f"mate {moves if score > 0 else -moves}"
    return f"cp {score}"


def main():
    # Send each line right away, otherwise the GUI sits waiting for output stuck in a buffer.
    sys.stdout.reconfigure(line_buffering=True)
    engine = Engine(10)
    board = chess.Board()

    def on_info(depth, score, nodes, seconds, pv):
        nps = int(nodes / seconds) if seconds else 0
        print(f"info depth {depth} score {format_score(score)} nodes {nodes} nps {nps} "
              f"time {int(seconds * 1000)} pv {' '.join(m.uci() for m in pv)}")

    # Read one command per line until the GUI says quit.
    for line in sys.stdin:
        tokens = line.split()
        if not tokens:
            continue
        command = tokens[0]
        if command == "uci":
            print("id name MajdChess")
            print("id author MajdHail")
            print("option name Skill Level type spin default 10 min 1 max 10")
            print("uciok")
        elif command == "isready":
            print("readyok")
        elif command == "ucinewgame":
            engine.new_game()
            board = chess.Board()
        elif command == "setoption" and "value" in tokens:
            name = " ".join(tokens[tokens.index("name") + 1:tokens.index("value")])
            if name.lower() == "skill level":
                engine.set_level(int(tokens[tokens.index("value") + 1]))
        elif command == "position":
            board = parse_position(tokens)
        elif command == "go":
            time_limit, max_depth = parse_go(tokens, board, engine)
            move = engine.search(board, time_limit=time_limit, max_depth=max_depth, on_info=on_info)
            print(f"bestmove {move.uci() if move else '0000'}")
        elif command == "quit":
            break


if __name__ == "__main__":
    main()
