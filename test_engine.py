"""Tests to check the engine still works after you change something.

Run with `python test_engine.py` or `pytest`.

Most tests are small puzzles with one clearly right answer. Positions are
written in FEN, a one-line text format for a chess position. You can paste
any FEN into lichess.org/editor to see the board.
"""
import chess

from engine import Engine
from evaluation import evaluate
from uci import parse_go


def best(fen, depth=4, level=10):
    """The engine's move for a position, as text like 'e2e4'."""
    return Engine(level).search(chess.Board(fen), time_limit=30, max_depth=depth).uci()


def test_eval_is_symmetric():
    # Swapping the colors should give the same score, or the evaluation favors one side.
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


def test_go_depth_keeps_time_limit():
    # En Croissant sends "go depth 30" and waits; a Python search would never reach that depth.
    engine = Engine(10)
    time_limit, max_depth = parse_go("go depth 30".split(), chess.Board(), engine)
    assert time_limit == engine.time_limit
    assert max_depth == 30


# Lets you run the tests without installing pytest.
if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
