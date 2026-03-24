"""Forward checking with singleton propagation for the Wordle CSP.

Forward checking is a look-ahead technique (AIMA Ch. 6.3.2) that immediately
prunes domains after each assignment. Instead of waiting to discover failures
deep in the search tree, it catches dead ends one step ahead by removing
inconsistent values from unassigned variables' domains.
"""
from algo.csp import CSPState


def forward_check(state, candidates=None):
    """Prune domains using candidate-based forward checking and singleton propagation.

    After any constraint or assignment change, intersect each position's domain
    with the letters that actually appear at that position in remaining candidates.
    Then run singleton propagation: if any domain drops to 1 value, fix it and
    repeat until no more singletons are created (fixpoint).

    Returns (updated_state, is_consistent, pruning_log).
    """
    domains = [set(d) for d in state.domains]
    assignment = dict(state.assignment)
    pruning_log = []

    # If candidates provided, intersect domains with actual letter occurrences
    if candidates:
        candidate_domains = [set() for _ in range(state.word_len)]
        for word in candidates:
            for i, ch in enumerate(word):
                candidate_domains[i].add(ch)
        for i in range(state.word_len):
            before = len(domains[i])
            domains[i] = domains[i] & candidate_domains[i]
            removed = before - len(domains[i])
            if removed > 0:
                pruning_log.append({
                    "position": i, "eliminated": removed,
                    "remaining": len(domains[i]),
                    "reason": "candidate intersection"
                })
            if len(domains[i]) == 0:
                return state, False, pruning_log

    # Singleton propagation loop — reach fixpoint
    changed = True
    while changed:
        changed = False
        for i in range(state.word_len):
            if len(domains[i]) == 0:
                return state, False, pruning_log
            if len(domains[i]) == 1 and i not in assignment:
                letter = next(iter(domains[i]))
                assignment[i] = letter
                pruning_log.append({
                    "position": i, "eliminated": letter,
                    "remaining": 1,
                    "reason": f"singleton fixed: '{letter}' at P{i}"
                })
                # Remove excluded letters that propagate
                for exc in state.excluded:
                    for j in range(state.word_len):
                        if exc in domains[j] and j != i:
                            domains[j].discard(exc)
                            if len(domains[j]) == 0:
                                return state, False, pruning_log
                            if len(domains[j]) == 1:
                                changed = True

    new_state = CSPState(
        state.word_len, domains, list(state.constraints),
        assignment, dict(state.must_have), set(state.excluded)
    )
    return new_state, True, pruning_log
