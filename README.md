# Majd Chess

A chess engine I made in Python with a desktop app to play against it.

It uses minimax with alpha-beta pruning, iterative deepening, a transposition table and quiescence search. You can pick from 10 difficulty levels.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## How it works

The engine does two things over and over:

1. **Evaluate**: look at a position and guess who is better, counting material and where pieces stand.
2. **Search**: try moves, then replies, then replies to those, and pick the move that turns out best if both sides play well.

Everything else is about making the search faster so it can look further ahead in the same time.

| File | What it does |
| --- | --- |
| `evaluation.py` | Scores a position. Start here, it's the simplest part. |
| `engine.py` | The search. The comment at the top explains all the terms. |
| `app.py` | Opens the desktop window and connects the page to the engine. |
| `index.html` | The board and buttons you see in the app. |
| `uci.py` | Lets other chess programs (like Cute Chess or Arena) use the engine. |
| `test_engine.py` | Small chess puzzles the engine has to solve. |

[python-chess](https://python-chess.readthedocs.io) handles the rules (legal moves, checkmate, etc.) so the code can focus on the engine itself.

## Test it

```bash
python test_engine.py
```

Run this after you change anything in `engine.py` or `evaluation.py`.

## Things to try

- Change a number in the piece-square tables in `evaluation.py` and see how the engine's style changes.
- Change the depth, time or noise for a level in `LEVELS` in `engine.py`.
- Set up two versions in Cute Chess with `python uci.py` and make them play each other to see if your change helped.

## Update the Mac app

`python app.py` always runs your latest code. The app in Applications is a frozen copy, so after changing something rebuild it:

```bash
pip install pyinstaller
pyinstaller --windowed --noconfirm --name "Majd Chess" --add-data "index.html:." app.py
rm -rf "/Applications/Majd Chess.app"
mv "dist/Majd Chess.app" /Applications/
rm -rf build dist "Majd Chess.spec"
```
