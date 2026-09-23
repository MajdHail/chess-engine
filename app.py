"""Browser UI: python web.py, then play at http://localhost:8000"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import chess

from engine import MATE, MATE_THRESHOLD, Engine

PAGE = Path(__file__).with_name("index.html")
engine = Engine()


def game_state(board, info=None):
    outcome = board.outcome()
    replay = chess.Board()
    san = []
    for move in board.move_stack:
        san.append(replay.san(move))
        replay.push(move)
    return {
        "fen": board.fen(),
        "moves": [m.uci() for m in board.move_stack],
        "san": san,
        "legal": [m.uci() for m in board.legal_moves],
        "turn": "white" if board.turn else "black",
        "check": chess.square_name(board.king(board.turn)) if board.is_check() else None,
        "result": outcome and {"score": outcome.result(), "reason": outcome.termination.name.lower().replace("_", " ")},
        "info": info,
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send(200, "text/html", PAGE.read_bytes())

    def do_POST(self):
        """Body: {moves: [uci], level: 1-10, think: bool}. Replays the game, optionally lets the engine move."""
        try:
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            board = chess.Board()
            for uci in request.get("moves", []):
                board.push_uci(uci)  # raises ValueError on illegal moves
        except (ValueError, TypeError, KeyError):
            self._send(400, "application/json", b'{"error": "bad request"}')
            return

        info = None
        if request.get("think") and not board.is_game_over():
            engine.set_level(request.get("level", 5))
            last = {}
            move = engine.search(board, on_info=lambda d, s, n, t, pv: last.update(depth=d, score=s, nodes=n))
            if last:
                # Engine scores are from the mover's side; the UI shows white's perspective.
                sign = 1 if board.turn == chess.WHITE else -1
                score = last["score"]
                mate = (MATE - abs(score) + 1) // 2 if abs(score) >= MATE_THRESHOLD else None
                info = {"depth": last["depth"], "nodes": last["nodes"], "score": sign * score,
                        "mate": mate and sign * (mate if score > 0 else -mate)}
            board.push(move)
        self._send(200, "application/json", json.dumps(game_state(board, info)).encode())

    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    # Single-threaded on purpose: one shared engine and its transposition table.
    server = HTTPServer(("127.0.0.1", 8000), Handler)
    print("Playing at http://localhost:8000  (Ctrl+C to stop)")
    webbrowser.open("http://localhost:8000")
    server.serve_forever()
