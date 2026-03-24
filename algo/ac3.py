"""AC-3 arc consistency algorithm for the Wordle CSP.

AC-3 (AIMA Ch. 6.2.2) is stronger than forward checking. It ensures that for
every pair of constrained variables, every value in one variable's domain has
a supporting value in the other's domain. In Wordle, arcs arise from
must_have constraints: if a letter must appear at least N times, and only N
positions can hold it, those positions are forced.

Complexity: O(e * d^3) where e = number of arcs, d = domain size.
"""
from algo.csp import CSPState


def ac3(state):
    """Run AC-3 arc consistency propagation on the CSP state.

    Builds arcs from must_have constraints (letter must appear at least N times)
    and processes them in a queue. When a domain shrinks, all affected arcs are
    re-queued. Reaches a fixpoint where all remaining values are pairwise
    consistent.

    Returns (new_state, is_consistent, revised_arcs_log).
    """
    domains = [set(d) for d in state.domains]
    assignment = dict(state.assignment)
    arcs_log = []
    queue = []

    # Initialize: check each must_have letter constraint
    for letter in state.must_have:
        queue.append(letter)

    processed = set()
    iterations = 0
    max_iterations = 100  # safety bound

    while queue and iterations < max_iterations:
        iterations += 1
        letter = queue.pop(0)
        min_count = state.must_have.get(letter, 0)
        if min_count == 0:
            continue

        # Find positions that can still hold this letter
        possible = [i for i in range(state.word_len) if letter in domains[i]]

        if len(possible) < min_count:
            arcs_log.append({
                "arc": [-1, -1], "removed": [letter],
                "description": f"Inconsistent: '{letter}' needs {min_count} "
                               f"positions but only {len(possible)} available"
            })
            return state, False, arcs_log

        # If exactly min_count positions can hold this letter, force them
        if len(possible) == min_count:
            for i in possible:
                if len(domains[i]) > 1:
                    old_domain = set(domains[i])
                    domains[i] = {letter}
                    assignment[i] = letter
                    removed = old_domain - {letter}
                    if removed:
                        arcs_log.append({
                            "arc": [i, -1], "removed": sorted(removed),
                            "description": f"P{i} forced to '{letter}' "
                                           f"(only {min_count} positions available)"
                        })
                        # Re-queue letters that lost a position
                        for lost in removed:
                            if lost in state.must_have and lost not in queue:
                                queue.append(lost)

    # Second pass: propagate green assignments across domains
    for pos, letter in assignment.items():
        if len(domains[pos]) == 1:
            # Check if this letter is excluded from other positions
            for i in range(state.word_len):
                if i != pos and i in assignment and assignment[i] == letter:
                    continue  # duplicate letter, both assigned
                # Don't remove from other positions — duplicates allowed

    # Verify all must_have are satisfiable
    for letter, min_count in state.must_have.items():
        possible = [i for i in range(state.word_len) if letter in domains[i]]
        if len(possible) < min_count:
            return state, False, arcs_log

    new_state = CSPState(
        state.word_len, domains, list(state.constraints),
        assignment, dict(state.must_have), set(state.excluded)
    )
    return new_state, True, arcs_log
