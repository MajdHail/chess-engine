# MajdChess

A chess engine written in Python, built around a **negamax alpha-beta search** with the classic
enhancements used by competitive engines. Play it in the terminal or load it into any UCI chess GUI,
with 10 difficulty levels from beginner to full strength.

[python-chess](https://python-chess.readthedocs.io/) is used only for board representation and legal
move generation. Everything that decides *which* move to play (search, pruning, move ordering,
evaluation, time management) is implemented here.

## Algorithms

| Technique | What it does |
|---|---|
| Negamax with alpha-beta pruning | Minimax search that skips branches that provably cannot change the result |
| Iterative deepening | Searches depth 1, 2, 3... so a best move is always ready when time runs out, and each iteration seeds move ordering for the next |
| Principal variation search | Searches the first move with a full window and the rest with a null window, re-searching only on a fail high |
| Transposition table (Zobrist hashing) | Caches results of positions reached through different move orders, with exact/lower/upper bound flags and mate-distance correction |
| Quiescence search | Keeps searching captures past the depth limit to avoid the horizon effect |
| Null-move pruning | Skips a turn; if the position is still too good for the opponent, prunes the node (disabled in pawn-only endings to avoid zugzwang errors) |
| Late move reductions | Searches late, quiet moves at reduced depth and re-searches if they surprise |
| Move ordering | TT move, then MVV-LVA captures, promotions, killer moves, and the history heuristic |
| Check extensions | Extends the search by one ply when in check so forcing lines are seen through |
| Tapered evaluation | PeSTO piece-square tables with separate middlegame and endgame scores blended by game phase |

On a laptop it reaches roughly depth 7 from the opening position in under 2 seconds.

## Difficulty levels

| Level | Max depth | Time per move | Root score noise |
|---|---|---|---|
| 1 | 1 | 0.1 s | ±300 cp |
| 2 | 1 | 0.2 s | ±150 cp |
| 3 | 2 | 0.3 s | ±100 cp |
| 4 | 2 | 0.5 s | ±60 cp |
| 5 | 3 | 1 s | ±30 cp |
| 6 | 4 | 1.5 s | ±15 cp |
| 7 | 5 | 2 s | none |
| 8 | 6 | 3 s | none |
| 9 | 8 | 5 s | none |
| 10 | unlimited | 10 s | none |

Lower levels combine a shallow search with random noise on the root move scores, so the engine makes
human-like mistakes instead of just playing the same move a bit slower.

## Usage

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python play.py --level 5 --color white   # play in the terminal
python uci.py                            # run as a UCI engine
python test_engine.py                    # run the tests
```

In the terminal game, type moves as SAN (`Nf3`, `O-O`) or UCI (`g1f3`). Commands:
`level N` changes difficulty mid-game, `hint` suggests a move, `undo` takes back your last move,
`flip` switches sides, `quit` exits.

### Using it in a chess GUI

Add `uci.py` as a UCI engine in Cute Chess, Arena, or Banksia (point it at `.venv/bin/python` with
`uci.py` as the argument). The difficulty is exposed as the `Skill Level` option (1 to 10).

## Project layout

```
engine.py       search: alpha-beta, TT, quiescence, pruning, move ordering, difficulty levels
evaluation.py   tapered PeSTO evaluation
uci.py          UCI protocol adapter
play.py         terminal game
test_engine.py  tactical and sanity tests (mate in 1/2, hanging pieces, stalemate avoidance)
```
