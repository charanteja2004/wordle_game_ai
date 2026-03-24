"""Master solver pipeline orchestrating all CSP techniques.

Coordinates AC-3, entropy ranking, backtracking with MRV+LCV, forward
checking, and constraint propagation. Tracks state and builds the search
graph for visualization (AIMA Ch. 3.1 — state space formulation).
"""
import math
from algo.csp import CSPState, apply_constraints
from algo.ac3 import ac3
from algo.forward_check import forward_check
from algo.entropy import rank_guesses, get_opener
from algo.backtracking import backtracking_search
from game.words import get_word_list, filter_candidates


class SolverState:
    """Complete solver state tracking CSP, candidates, graph, and trace."""
    def __init__(self, word_len, csp, candidates, all_words):
        self.word_len, self.csp = word_len, csp
        self.candidates, self.all_words = candidates, all_words
        self.guesses, self.results = [], []
        self.graph_nodes, self.graph_edges, self.trace = [], [], []
        self.total_start, self.step = len(candidates), 0


def initialize(word_length):
    """Set up initial solver state with full domains and word list."""
    csp = CSPState.initial(word_length)
    words = get_word_list(word_length)
    state = SolverState(word_length, csp, list(words), words)
    state.graph_nodes.append({"data": {"id": "n0",
        "label": f"Start\n{len(words)} candidates", "type": "start", "candidates": len(words)}})
    state.trace.append({"step": 0, "description": f"Initialized: {len(words)} candidates",
                         "variable": None, "domains_reduced": 0, "status": "reduced"})
    return state


def next_guess(solver):
    """Pipeline: AC-3 → filter → entropy rank → backtracking cross-check → pick best."""
    solver.step += 1
    csp_after, consistent, ac3_log = ac3(solver.csp)
    ac3_arcs = len(ac3_log)
    if consistent:
        solver.csp = csp_after
    csp_after, fc_ok, fc_log = forward_check(solver.csp, solver.candidates)
    pruned = sum(e.get("eliminated", 0) if isinstance(e.get("eliminated"), int) else 1 for e in fc_log)
    if fc_ok:
        solver.csp = csp_after
    solver.candidates = filter_candidates(solver.candidates, solver.csp)
    n = len(solver.candidates)

    ranked = []
    if n == 0:
        return None, _prediction(solver, []), {"ac3_arcs": ac3_arcs, "domains_pruned": pruned,
                                            "backtrack_steps": 0, "entropy_of_chosen": 0}
    if n <= 2:
        guess, ent = solver.candidates[0], 0.0
    elif not solver.guesses:
        guess = get_opener(solver.word_len)
        if guess not in solver.all_words:
            guess = solver.candidates[0]
        ent = 0.0  # Skip entropy calc for precomputed opener
    else:
        ranked = rank_guesses(solver.candidates, solver.all_words, solver.csp)
        guess = ranked[0]["word"] if ranked else solver.candidates[0]
        ent = ranked[0]["entropy"] if ranked else 0.0

    # Only run backtracking when candidate set is small enough to matter
    bt_steps = 0
    if n <= 20:
        bt_word, bt_trace = backtracking_search(solver.csp, solver.candidates)
        bt_steps = len(bt_trace)
        cand_set = set(solver.candidates)
        if guess not in cand_set and bt_word and bt_word in cand_set:
            guess = bt_word

    nid = f"n{solver.step}"
    solver.graph_nodes.append({"data": {"id": nid,
        "label": f"{guess}\n{n} candidates", "type": "selected", "candidates": n}})
    if solver.step > 0:
        solver.graph_edges.append({"data": {"id": f"e{solver.step-1}-{solver.step}",
            "source": f"n{solver.step-1}",
            "target": nid, "label": f"H={ent:.2f}"}})

    # Add top-5 alternatives as explored nodes branching from the parent
    # Prefer candidate words so alternatives are meaningful at each step
    if ranked:
        cand_set = set(solver.candidates)
        cand_alts = [r for r in ranked if r["word"] != guess and r["word"] in cand_set]
        non_cand_alts = [r for r in ranked if r["word"] != guess and r["word"] not in cand_set]
        top5 = (cand_alts + non_cand_alts)[:5]
    else:
        top5 = []
    for rank_i, r in enumerate(top5):
        if r["word"] == guess:
            continue  # skip the chosen one — it's already the selected node
        alt_id = f"n{solver.step}_alt{rank_i}"
        solver.graph_nodes.append({"data": {"id": alt_id,
            "label": f"{r['word']}\nH={r['entropy']:.2f}",
            "type": "explored", "candidates": n}})
        if solver.step > 0:
            solver.graph_edges.append({"data": {
                "id": f"e{solver.step-1}-{alt_id}",
                "source": f"n{solver.step-1}",
                "target": alt_id, "label": f"#{rank_i+1}"}})

    solver.trace.append({"step": solver.step, "variable": None, "domains_reduced": pruned,
        "description": f"Guess '{guess}': entropy={ent:.2f}, {n} candidates", "status": "assigned"})
    stats = {"entropy_of_chosen": round(ent, 4), "ac3_arcs_revised": ac3_arcs,
             "domains_pruned": pruned, "backtrack_steps": bt_steps}
    # Pass ranked results to avoid recomputing in _prediction
    return guess, _prediction(solver, ranked), stats


def process_result(solver, guess, result):
    """Apply guess result: constraints → forward check → AC-3 → filter."""
    solver.guesses.append(guess)
    solver.results.append(result)
    solver.csp = apply_constraints(solver.csp, guess, result)
    solver.csp, _, _ = forward_check(solver.csp, solver.candidates)
    solver.csp, _, _ = ac3(solver.csp)
    solver.candidates = filter_candidates(solver.candidates, solver.csp)
    n = len(solver.candidates)
    solver.trace.append({"step": solver.step, "variable": None, "domains_reduced": 0,
        "description": f"After '{guess}': {n} candidates remain", "status": "reduced"})
    pid = f"n{solver.step}p"
    solver.graph_nodes.append({"data": {"id": pid,
        "label": f"Pruned\n-{solver.total_start - n}", "type": "pruned", "candidates": n}})
    solver.graph_edges.append({"data": {"id": f"e{solver.step}-{pid}",
        "source": f"n{solver.step}", "target": pid,
        "label": "\u2192".join(result[:3])}})
    return solver


def _prediction(solver, precomputed_ranked=None):
    """Build prediction data for frontend visualization."""
    n = len(solver.candidates)
    if precomputed_ranked is not None:
        ranked = precomputed_ranked[:5]
    else:
        ranked = rank_guesses(solver.candidates, solver.all_words, solver.csp, top_k=5) if n > 0 else []
    sizes = [len(d) for d in solver.csp.domains]
    elim = (1 - n / solver.total_start) * 100 if solver.total_start > 0 else 0
    est = max(1, round(math.log2(n))) if n > 1 else (0 if n == 1 else 1)
    return {
        "top_candidates": [{"word": r["word"], "score": r["score"],
            "entropy": r["entropy"], "is_candidate": r.get("is_candidate", True)} for r in ranked],
        "candidates_remaining": n, "domain_sizes": sizes,
        "elimination_rate": round(elim, 1), "estimated_remaining_guesses": est,
        "confidence": round(1/n, 4) if n > 0 else 0}


def serialize_state(solver):
    """Convert SolverState to JSON-safe dict for session storage."""
    return {"word_len": solver.word_len, "guesses": solver.guesses,
            "results": solver.results, "step": solver.step}


def deserialize_state(data):
    """Rebuild SolverState from session data by replaying guesses."""
    solver = initialize(data["word_len"])
    for i, (g, r) in enumerate(zip(data["guesses"], data["results"])):
        solver.step = i + 1
        
        # Reconstruct the selected node for the graph
        n = len(solver.candidates)
        nid = f"n{solver.step}"
        solver.graph_nodes.append({"data": {"id": nid,
            "label": f"{g}\n{n} candidates", "type": "selected", "candidates": n}})
        solver.graph_edges.append({"data": {"id": f"e{solver.step-1}-{solver.step}",
            "source": f"n{solver.step-1}", "target": nid, "label": ""}})
            
        solver = process_result(solver, g, r)
    solver.step = data.get("step", len(data["guesses"]))
    return solver
