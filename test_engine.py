"""Run with `python test_engine.py` or `pytest`."""
import chess

from engine import Engine
from evaluation import evaluate


def best(fen, depth=4, level=10):
    return Engine(level).search(chess.Board(fen), time_limit=30, max_depth=depth).uci()


def test_eval_is_symmetric():
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    assert evaluate(board) == evaluate(board.mirror())


def test_mate_in_one():
    assert best("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", depth=2) == "a1a8"


def test_mate_in_two():
    # Queen sacrifice then smothered-style finish: 1.Qg8+ Rxg8 2.Nf7#
    assert best("r5rk/5Qpp/7N/8/8/8/8/6K1 w - - 0 1", depth=4) == "f7g8"


def test_takes_hanging_queen():
    assert best("4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1", depth=3) == "d1d5"


def test_avoids_stalemate_when_winning():
    board = chess.Board("7k/8/6QK/8/8/8/8/8 w - - 0 1")
    move = Engine(10).search(board, time_limit=30, max_depth=3)
    board.push(move)
    assert not board.is_stalemate()


def test_every_level_returns_legal_move():
    board = chess.Board()
    for level in range(1, 11):
        assert Engine(level).search(board, time_limit=0.2) in board.legal_moves


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
