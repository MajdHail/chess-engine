"""Desktop app: python app.py opens the game in a native window."""
import sys
from pathlib import Path

import chess
import webview

from engine import MATE, MATE_THRESHOLD, Engine

# PyInstaller unpacks bundled files to _MEIPASS, not next to this script.
PAGE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "index.html"


def san_list(board, moves):
    board = board.copy()
    out = []
    for move in moves:
        out.append(board.san(move))
        board.push(move)
    return out


def game_state(board, info=None):
    outcome = board.outcome()
    return {
        "fen": board.fen(),
        "moves": [m.uci() for m in board.move_stack],
        "san": san_list(chess.Board(), board.move_stack),
        "legal": [m.uci() for m in board.legal_moves],
        "turn": "white" if board.turn else "black",
        "check": chess.square_name(board.king(board.turn)) if board.is_check() else None,
        "result": outcome and {"score": outcome.result(), "reason": outcome.termination.name.lower().replace("_", " ")},
        "info": info,
    }


class Api:
    """Methods here are callable from the page as window.pywebview.api.<name>()."""

    def __init__(self):
        self.engine = Engine()

    def play(self, moves, think=False, level=5):
        """Replay `moves` from the start position and optionally let the engine answer."""
        board = chess.Board()
        for uci in moves:
            board.push_uci(uci)  # raises on illegal moves, which rejects the JS promise

        info = None
        if think and not board.is_game_over():
            self.engine.set_level(level)
            last = {}
            move = self.engine.search(board, on_info=lambda d, s, n, t, pv: last.update(depth=d, score=s, nodes=n, seconds=t, pv=pv))
            if last:
                # Engine scores are from the mover's side; the UI shows white's perspective.
                sign = 1 if board.turn == chess.WHITE else -1
                score = last["score"]
                mate = (MATE - abs(score) + 1) // 2 if abs(score) >= MATE_THRESHOLD else None
                info = {"depth": last["depth"], "nodes": last["nodes"], "seconds": round(last["seconds"], 2),
                        "score": sign * score, "mate": mate and sign * (mate if score > 0 else -mate),
                        "pv": san_list(board, last["pv"])}
            board.push(move)
        return game_state(board, info)


if __name__ == "__main__":
    webview.create_window("Majd Chess", str(PAGE), js_api=Api(), width=1120, height=800,
                          min_size=(760, 600), background_color="#0e0e0e")
    webview.start()
