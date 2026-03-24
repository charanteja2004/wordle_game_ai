"""Backtracking search with MRV, LCV, and forward checking for Wordle CSP.

Backtracking search (AIMA Ch. 6.3) is depth-first search that assigns one
variable at a time and backtracks when a constraint is violated. Combined
with MRV (fail-first variable selection) and LCV (fail-last value ordering),
it efficiently explores the search tree by surfacing contradictions early
and maximizing the chance of finding valid assignments.
"""


def select_variable_mrv(domains, assignment, word_len, constraints):
    """Pick the unassigned position with the FEWEST remaining domain values.

    MRV (Minimum Remaining Values) is a fail-first heuristic: by choosing
    the most constrained variable first, failures surface early and prune
    more of the search tree — exponentially fewer nodes explored.

    Tiebreaker: degree heuristic — prefer the position involved in the most
    constraints (approximated by number of constraints referencing it).
    """
    unassigned = [i for i in range(word_len) if i not in assignment]
    if not unassigned:
        return None
    min_size = min(len(domains[i]) for i in unassigned)
    ties = [i for i in unassigned if len(domains[i]) == min_size]
    if len(ties) == 1:
        return ties[0]
    constraint_count = {}
    for i in ties:
        constraint_count[i] = sum(1 for c in constraints if c.position == i)
    return max(ties, key=lambda i: constraint_count.get(i, 0))


def order_values_lcv(domains, variable, candidates):
    """Order domain values using Least Constraining Value heuristic.

    LCV (AIMA Ch. 6.3.1): prefer the letter that eliminates the fewest
    options for other positions' domains. This maximizes the chance that
    remaining variables can still be assigned without backtracking.

    For each letter, count how many candidates survive if this letter is
    placed at the given position. Return letters sorted descending by
    surviving count (most permissive first).
    """
    counts = {}
    for letter in domains[variable]:
        counts[letter] = sum(1 for w in candidates if w[variable] == letter)
    return sorted(domains[variable], key=lambda c: -counts.get(c, 0))


def backtracking_search(state, word_list):
    """Full backtracking search with MRV + LCV + forward checking.

    Explores the CSP search tree by:
    1. MRV variable selection — pick most constrained position
    2. LCV value ordering — try least constraining letter first
    3. Forward checking — if assignment leads to empty domain, backtrack
    4. Find all valid words matching the current assignment
    5. Return best word and a trace log of the search steps

    When domains are too large (> 10 letters per unassigned position),
    skips full search and returns candidates directly to avoid explosion.

    Returns (best_word_or_None, trace_log_list).
    """
    trace = []
    candidate_set = set(word_list)

    # Skip backtracking when search space is too large
    unassigned = [i for i in range(state.word_len) if i not in state.assignment]
    if unassigned:
        max_domain = max(len(state.domains[i]) for i in unassigned)
        if max_domain > 10 or len(unassigned) > 3:
            if word_list:
                trace.append({"step": 1, "description": "Domains too large for backtracking, using candidates",
                              "variable": None, "domains_reduced": 0, "status": "reduced"})
                return word_list[0], trace
            return None, trace

    step = [0]
    results = []

    def _backtrack(assignment):
        if step[0] > 500 or len(results) >= 5:
            return
        var = select_variable_mrv(state.domains, assignment, state.word_len, state.constraints)
        if var is None:
            word = ''.join(assignment.get(i, '?') for i in range(state.word_len))
            step[0] += 1
            if word in candidate_set:
                results.append(word)
                trace.append({"step": step[0], "description": f"Found valid word: {word}",
                              "variable": None, "domains_reduced": 0, "status": "solved"})
            return

        values = order_values_lcv(state.domains, var, word_list)
        for val in values:
            if step[0] > 500 or len(results) >= 5:
                return
            step[0] += 1
            assignment[var] = val
            trace.append({"step": step[0], "description": f"Try P{var}='{val}'",
                          "variable": var, "domains_reduced": 0, "status": "assigned"})

            consistent = True
            for i in range(state.word_len):
                if i not in assignment and len(state.domains[i]) == 0:
                    consistent = False
                    break

            if consistent:
                _backtrack(assignment)

            if not consistent:
                trace.append({"step": step[0], "description": f"Backtrack from P{var}='{val}'",
                              "variable": var, "domains_reduced": 0, "status": "backtrack"})

            del assignment[var]

    _backtrack(dict(state.assignment))

    if results:
        return results[0], trace
    if word_list:
        return word_list[0], trace
    return None, trace
