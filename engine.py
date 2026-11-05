"""The search: how the engine decides which move to play.

The core idea is minimax. The engine imagines every move it could make, then
every reply the opponent could make, and so on, and picks the move that works
out best assuming the opponent also plays their best. The number of positions
explodes quickly, so most of this file is tricks to skip positions that
cannot change the answer:

- Negamax: minimax written so one function handles both sides. A position
  that is +3 for me is -3 for you, so we just flip the sign each ply.
- Alpha-beta pruning: stop looking at a move as soon as we know it is worse
  than something we already found.
- Iterative deepening: search 1 move deep, then 2, then 3... until time runs
  out. Each round also tells the next one which moves to try first.
- Transposition table (TT): a cache of positions we already searched, because
  the same position can be reached by different move orders.
- Quiescence search: at the end of the search, keep looking at captures so we
  never stop in the middle of a trade (the "horizon effect").
- Move ordering: try the most promising moves first so alpha-beta prunes more.
- Null-move pruning, late move reductions, principal variation search: extra
  shortcuts that search unlikely moves less deeply.

Words you will see a lot:
- ply: one move by one side (a "move" in chess notation is two plies).
- depth: how many more plies we still want to look ahead.
- alpha: the best score we (the side to move) are already guaranteed.
- beta: the best score the opponent is already guaranteed. If we find
  something >= beta, the opponent would never let us reach this position,
  so we can stop searching it (a "beta cutoff").
- centipawns: scores are in hundredths of a pawn, so 100 = one pawn.
"""
import math
import random
import time
from collections import defaultdict

import chess
import chess.polyglot

from evaluation import evaluate

INF = 1_000_000
# Mate scores subtract the ply count, so the engine prefers the quickest mate.
MATE = 100_000
MATE_THRESHOLD = MATE - 1000
# Transposition table entry types: the stored score is exact, a floor or a ceiling.
EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX_ENTRIES = 1_000_000

# Level: (max depth, seconds per move, centipawn noise).
# Weaker levels search less deeply, and noise makes them blunder on purpose.
LEVELS = {
    1: (1, 0.1, 300),
    2: (1, 0.2, 150),
    3: (2, 0.3, 100),
    4: (2, 0.5, 60),
    5: (3, 1.0, 30),
    6: (4, 1.5, 15),
    7: (5, 2.0, 0),
    8: (6, 3.0, 0),
    9: (8, 5.0, 0),
    10: (64, 10.0, 0),
}


class TimeUp(Exception):
    """Raised deep inside the search to bail out as soon as time runs out."""


class Engine:
    def __init__(self, level=5):
        self.tt = {}
        self.set_level(level)

    def set_level(self, level):
        self.level = max(1, min(10, int(level)))
        self.max_depth, self.time_limit, self.noise = LEVELS[self.level]

    def new_game(self):
        self.tt.clear()

    def search(self, board, time_limit=None, max_depth=None, on_info=None):
        """Return the best move for `board`, searching deeper until time or depth runs out.

        on_info(depth, score, nodes, seconds, pv) is called after each completed iteration.
        """
        board = board.copy()
        legal = list(board.legal_moves)
        if not legal:
            return None
        if len(legal) == 1:
            return legal[0]

        start = time.monotonic()
        limit = self.time_limit if time_limit is None else time_limit
        self.deadline = start + limit
        self.nodes = 0  # positions visited, for stats only
        self.killers = defaultdict(list)  # quiet moves that caused a cutoff, per ply
        self.history = defaultdict(int)  # how often each quiet move caused a cutoff
        # Wiping the whole table is simple but loses good entries. Depth-preferred
        # replacement would keep them if memory ever becomes a limit.
        if len(self.tt) > TT_MAX_ENTRIES:
            self.tt.clear()

        # Keep the result of the last finished depth and discard one cut off by the clock.
        best_move = None
        for depth in range(1, (max_depth or self.max_depth) + 1):
            try:
                move, score = self._root(board, depth, best_move)
            except TimeUp:
                break
            best_move = move
            elapsed = time.monotonic() - start
            if on_info:
                on_info(depth, score, self.nodes, elapsed, self._pv(board, move, depth))
            if abs(score) >= MATE_THRESHOLD:
                break  # found a forced mate, searching deeper won't help
            # Each iteration costs several times the last one, so don't start one we can't finish.
            if elapsed > limit / 2:
                break
        return best_move or legal[0]

    def _root(self, board, depth, prev_best):
        """Search every legal move at the top of the tree and return (best move, its score)."""
        alpha = -INF
        best_move, best_score, best_key = None, -INF, -math.inf
        # prev_best is the best move from the last iteration, so it gets searched first.
        for move in self._ordered_moves(board, prev_best, 0):
            board.push(move)
            if self.noise:
                # Noise needs an exact score for every root move, so it picks between real options.
                score = -self._negamax(board, depth - 1, -INF, INF, 1)
            else:
                score = -self._negamax(board, depth - 1, -INF, -alpha, 1)
            board.pop()
            # Rank moves by score plus noise, but report the real score to the UI.
            key = score + random.randint(-self.noise, self.noise) if self.noise else score
            if key > best_key:
                best_key, best_move, best_score = key, move, score
            alpha = max(alpha, score)
        return best_move, best_score

    def _check_time(self):
        self.nodes += 1
        # Reading the clock is slow, so only check every 2048 positions.
        if self.nodes & 2047 == 0 and time.monotonic() > self.deadline:
            raise TimeUp

    def _negamax(self, board, depth, alpha, beta, ply, allow_null=True):
        """Score `board` from the side to move's point of view.

        The score is only exact if it lands between alpha and beta. Outside that
        window we just know "it's at least beta" or "it's at most alpha", which is
        all the caller needs to decide it won't pick this line.
        """
        self._check_time()
        if board.is_repetition(2) or board.halfmove_clock >= 100 or board.is_insufficient_material():
            return 0  # draw

        # Check extension: never stop searching while in check, the position is too sharp.
        in_check = board.is_check()
        if in_check:
            depth += 1
        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply)

        # Look up this position's Zobrist hash in the transposition table.
        key = chess.polyglot.zobrist_hash(board)
        tt_move = None
        entry = self.tt.get(key)
        if entry:
            tt_depth, flag, tt_score, tt_move = entry
            # Only trust the cached score if it was searched at least as deep as we need.
            if tt_depth >= depth:
                tt_score = _score_from_tt(tt_score, ply)
                if flag == EXACT:
                    return tt_score
                if flag == LOWER and tt_score >= beta:
                    return tt_score
                if flag == UPPER and tt_score <= alpha:
                    return tt_score

        # Null-move pruning: if we can pass and still beat beta, this position is too good.
        # Pawn-only endings are excluded because zugzwang makes passing unrealistically safe.
        has_pieces = board.occupied_co[board.turn] & ~(board.pawns | board.kings)
        if allow_null and not in_check and depth >= 3 and has_pieces and abs(beta) < MATE_THRESHOLD:
            board.push(chess.Move.null())
            score = -self._negamax(board, depth - 3, -beta, -beta + 1, ply + 1, False)
            board.pop()
            if score >= beta:
                return beta

        moves = self._ordered_moves(board, tt_move, ply)
        if not moves:
            # No legal moves: checkmate if in check (worse the sooner), otherwise stalemate.
            return -MATE + ply if in_check else 0

        original_alpha = alpha
        best_score, best_move = -INF, None
        for i, move in enumerate(moves):
            quiet = not board.is_capture(move) and not move.promotion
            board.push(move)
            if i == 0:
                # First move is probably the best one (thanks to move ordering), search it fully.
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            else:
                # PVS and LMR: test later moves with a cheap zero-width window,
                # searching late quiet moves one ply shallower.
                reduction = 1 if depth >= 3 and i >= 4 and quiet and not in_check and not board.is_check() else 0
                score = -self._negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
                # The cheap search says this move might be better after all, so search it properly.
                if score > alpha and (reduction or score < beta):
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()

            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, score)
            if alpha >= beta:
                # Beta cutoff. Remember quiet moves, since they often work in sibling positions.
                if quiet:
                    killers = self.killers[ply]
                    if move not in killers:
                        killers.insert(0, move)
                        del killers[2:]
                    self.history[(board.turn, move.from_square, move.to_square)] += depth * depth
                break

        # Save the result in the TT, noting whether it's exact or just a bound.
        if best_score <= original_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, flag, _score_to_tt(best_score, ply), best_move)
        return best_score

    def _quiesce(self, board, alpha, beta, ply):
        """Keep searching captures only, until the position is quiet enough to evaluate.

        Without this, the engine might stop right after QxP and think it won a pawn,
        not seeing that the queen gets taken back next move.
        """
        self._check_time()
        # Stand pat because not capturing is always allowed, so the current eval is a floor.
        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return stand_pat
        alpha = max(alpha, stand_pat)
        for move in sorted(board.generate_legal_captures(), key=lambda m: _mvv_lva(board, m), reverse=True):
            board.push(move)
            score = -self._quiesce(board, -beta, -alpha, ply + 1)
            board.pop()
            if score >= beta:
                return score
            alpha = max(alpha, score)
        return alpha

    def _ordered_moves(self, board, tt_move, ply):
        """Sort moves best-guess first. Good ordering is what makes alpha-beta fast."""
        killers = self.killers[ply]

        # Bigger number = searched earlier.
        def priority(move):
            if move == tt_move:
                return 10_000_000
            if board.is_capture(move):
                return 1_000_000 + _mvv_lva(board, move)
            if move.promotion:
                return 900_000 + move.promotion
            if move in killers:
                return 800_000
            return min(self.history[(board.turn, move.from_square, move.to_square)], 799_999)

        return sorted(board.legal_moves, key=priority, reverse=True)

    def _pv(self, board, first_move, depth):
        """Follow best moves through the TT to reconstruct the principal variation.

        The principal variation (PV) is the line the engine expects both sides to play.
        """
        pv = [first_move]
        board = board.copy()
        board.push(first_move)
        while len(pv) < depth:
            entry = self.tt.get(chess.polyglot.zobrist_hash(board))
            if not entry or entry[3] is None or entry[3] not in board.legal_moves:
                break
            pv.append(entry[3])
            board.push(entry[3])
        return pv


def _mvv_lva(board, move):
    """Most valuable victim, least valuable attacker: PxQ first, QxP last."""
    victim = board.piece_type_at(move.to_square) or chess.PAWN  # en passant lands on an empty square
    return 10 * victim - board.piece_type_at(move.from_square)


# The TT stores mate scores relative to the node, so a hit at another ply
# still reports the right distance to mate.
def _score_to_tt(score, ply):
    if score >= MATE_THRESHOLD:
        return score + ply
    if score <= -MATE_THRESHOLD:
        return score - ply
    return score


def _score_from_tt(score, ply):
    if score >= MATE_THRESHOLD:
        return score - ply
    if score <= -MATE_THRESHOLD:
        return score + ply
    return score
