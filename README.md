# Majd Chess

A chess engine I built in Python, with a desktop app to play against it.

I used python-chess for the board and legal moves. The part that actually picks moves (search and evaluation) is my own.

## How it works

The engine uses minimax with alpha-beta pruning. On top of that I added:

- iterative deepening, so it always has a move ready when time runs out
- a transposition table with Zobrist hashing so it doesn't re-search the same positions
- quiescence search so it doesn't stop in the middle of a capture sequence
- null move pruning and late move reductions to search deeper
- move ordering (MVV-LVA, killer moves, history heuristic)
- an evaluation based on the PeSTO piece-square tables, blended between middlegame and endgame

It gets to around depth 7 from the starting position in a couple of seconds.

## Difficulty

There are 10 levels. Lower levels search fewer moves ahead and add some randomness to their choices so they make mistakes like a real beginner would. Level 10 searches as deep as it can in 10 seconds.

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

After each move the app shows what the engine was thinking: how deep it looked, the line it expects, and who it thinks is winning.

It also speaks UCI (`python uci.py`), so you can load it into a chess GUI like Cute Chess or Arena.

To build a Mac app:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Majd Chess" --add-data "index.html:." app.py
```

Tests: `python test_engine.py`
