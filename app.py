"""The desktop app: `python app.py` opens the game in its own window.

How it fits together:
- index.html is the whole user interface (board, buttons, explanation panel).
- pywebview shows that page in a native window, like a mini browser.
- The page calls Api.play() below through pywebview's JavaScript bridge, and
  Python sends back the new game state as a dictionary (it arrives as a JS object).

The page doesn't know any chess rules itself. It asks Python for the list of
legal moves and just draws whatever state it gets back.
"""

import sys
from pathlib import Path

import chess
import webview

from engine import MATE, MATE_THRESHOLD, Engine

# PyInstaller unpacks bundled files to _MEIPASS, not next to this script.
PAGE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "index.html"


def san_list(board, moves):
    """Turn moves like 'g1f3' into readable notation like 'Nf3'."""
    board = board.copy()
    out = []
    for move in moves:
        out.append(board.san(move))
        board.push(move)
    return out


def game_state(board, info=None):
    """Everything the page needs to draw the board, packed into a dictionary."""
    outcome = board.outcome()
    return {
        "fen": board.fen(),  # the whole position as one line of text
        "moves": [m.uci() for m in board.move_stack],
        "san": san_list(chess.Board(), board.move_stack),
        "legal": [m.uci() for m in board.legal_moves],
        "turn": "white" if board.turn else "black",
        "check": chess.square_name(board.king(board.turn)) if board.is_check() else None,
        "result": outcome
        and {
            "score": outcome.result(),
            "reason": outcome.termination.name.lower().replace("_", " "),
        },
        "info": info,  # what the engine found while thinking, shown in the explanation panel
    }


class Api:
    """Methods here are callable from the page as window.pywebview.api.<name>()."""

    def __init__(self):
        self.engine = Engine()

    def play(self, moves, think=False, level=5):
        """Replay `moves` from the start position and optionally let the engine answer.

        The page sends the full move list every time instead of one move, so
        Python doesn't have to remember anything between calls. That also makes
        undo easy: just send a shorter list.
        """
        board = chess.Board()
        for uci in moves:
            board.push_uci(uci)  # raises on illegal moves, which rejects the JS promise

        info = None
        if think and not board.is_game_over():
            self.engine.set_level(level)
            # Keep whatever the deepest finished search reported.
            last = {}
            move = self.engine.search(
                board,
                on_info=lambda d, s, n, t, pv: last.update(
                    depth=d, score=s, nodes=n, seconds=t, pv=pv
                ),
            )
            if last:
                # Engine scores are from the mover's side; the UI shows white's perspective.
                sign = 1 if board.turn == chess.WHITE else -1
                score = last["score"]
                # Turn a mate score back into "mate in N moves" (N counts full moves, not plies).
                mate = (MATE - abs(score) + 1) // 2 if abs(score) >= MATE_THRESHOLD else None
                info = {
                    "depth": last["depth"],
                    "nodes": last["nodes"],
                    "seconds": round(last["seconds"], 2),
                    "score": sign * score,
                    "mate": mate and sign * (mate if score > 0 else -mate),
                    "pv": san_list(board, last["pv"]),
                }
            board.push(move)
        return game_state(board, info)


if __name__ == "__main__":
    webview.create_window(
        "Majd Chess",
        str(PAGE),
        js_api=Api(),
        width=1120,
        height=800,
        min_size=(760, 600),
        background_color="#0e0e0e",
    )
    webview.start()
