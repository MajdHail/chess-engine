"""Search: negamax with alpha-beta pruning, iterative deepening and the usual enhancements.

- Principal variation search (null-window re-search for non-first moves)
- Transposition table keyed by Zobrist hash
- Quiescence search on captures to avoid the horizon effect
- Null-move pruning and late move reductions
- Move ordering: TT move, MVV-LVA captures, killer moves, history heuristic
- Check extensions and mate-distance aware scores
"""
import math
import random
import time
from collections import defaultdict

import chess
import chess.polyglot

from evaluation import evaluate

INF = 1_000_000
MATE = 100_000
MATE_THRESHOLD = MATE - 1000
EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX_ENTRIES = 1_000_000

# level: (max depth, seconds per move, random noise in centipawns added to root scores)
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
    pass


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
        self.nodes = 0
        self.killers = defaultdict(list)
        self.history = defaultdict(int)
        # ponytail: whole-table wipe when full, replace with depth-preferred buckets if memory matters
        if len(self.tt) > TT_MAX_ENTRIES:
            self.tt.clear()

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
                break
            # Each iteration costs several times the last one, so don't start one we can't finish.
            if elapsed > limit / 2:
                break
        return best_move or legal[0]

    def _root(self, board, depth, prev_best):
        alpha = -INF
        best_move, best_score, best_key = None, -INF, -math.inf
        for move in self._ordered_moves(board, prev_best, 0):
            board.push(move)
            if self.noise:
                # Weaker levels need exact scores for every root move so the noise
                # picks between real alternatives instead of pruning bounds.
                score = -self._negamax(board, depth - 1, -INF, INF, 1)
            else:
                score = -self._negamax(board, depth - 1, -INF, -alpha, 1)
            board.pop()
            key = score + random.randint(-self.noise, self.noise) if self.noise else score
            if key > best_key:
                best_key, best_move, best_score = key, move, score
            alpha = max(alpha, score)
        return best_move, best_score

    def _check_time(self):
        self.nodes += 1
        if self.nodes & 2047 == 0 and time.monotonic() > self.deadline:
            raise TimeUp

    def _negamax(self, board, depth, alpha, beta, ply, allow_null=True):
        self._check_time()
        if board.is_repetition(2) or board.halfmove_clock >= 100 or board.is_insufficient_material():
            return 0

        in_check = board.is_check()
        if in_check:
            depth += 1
        if depth <= 0:
            return self._quiesce(board, alpha, beta, ply)

        key = chess.polyglot.zobrist_hash(board)
        tt_move = None
        entry = self.tt.get(key)
        if entry:
            tt_depth, flag, tt_score, tt_move = entry
            if tt_depth >= depth:
                tt_score = _score_from_tt(tt_score, ply)
                if flag == EXACT:
                    return tt_score
                if flag == LOWER and tt_score >= beta:
                    return tt_score
                if flag == UPPER and tt_score <= alpha:
                    return tt_score

        # Null move: if passing still beats beta, a real move surely will. Unsafe in
        # zugzwang-prone pawn endings, hence the non-pawn material requirement.
        has_pieces = board.occupied_co[board.turn] & ~(board.pawns | board.kings)
        if allow_null and not in_check and depth >= 3 and has_pieces and abs(beta) < MATE_THRESHOLD:
            board.push(chess.Move.null())
            score = -self._negamax(board, depth - 3, -beta, -beta + 1, ply + 1, False)
            board.pop()
            if score >= beta:
                return beta

        moves = self._ordered_moves(board, tt_move, ply)
        if not moves:
            return -MATE + ply if in_check else 0

        original_alpha = alpha
        best_score, best_move = -INF, None
        for i, move in enumerate(moves):
            quiet = not board.is_capture(move) and not move.promotion
            board.push(move)
            if i == 0:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            else:
                reduction = 1 if depth >= 3 and i >= 4 and quiet and not in_check and not board.is_check() else 0
                score = -self._negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
                if score > alpha and (reduction or score < beta):
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()

            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, score)
            if alpha >= beta:
                if quiet:
                    killers = self.killers[ply]
                    if move not in killers:
                        killers.insert(0, move)
                        del killers[2:]
                    self.history[(board.turn, move.from_square, move.to_square)] += depth * depth
                break

        if best_score <= original_alpha:
            flag = UPPER
        elif best_score >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, flag, _score_to_tt(best_score, ply), best_move)
        return best_score

    def _quiesce(self, board, alpha, beta, ply):
        self._check_time()
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
        killers = self.killers[ply]

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
        """Follow best moves through the TT to reconstruct the principal variation."""
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


# Mate scores are stored relative to the node, not the root, so a TT hit at a
# different ply still reports the correct distance to mate.
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
