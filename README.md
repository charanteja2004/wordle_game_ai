# Wordle Solver — Classical AI Approach

## Overview

This project solves Wordle using classical AI constraint satisfaction techniques combined with information theory. No machine learning, neural networks, or language models are used. The solver models the puzzle as a CSP where variables are letter positions, domains are possible letters, and constraints come from guess feedback. It uses entropy-based word selection to maximize information gain per guess, combined with AC-3 arc consistency, forward checking with singleton propagation, and backtracking with MRV+LCV heuristics.

## AI Techniques (with AIMA references)

1. **Constraint Satisfaction Problems (CSP)** — AIMA Chapter 6: modeling Wordle as variables, domains, constraints
2. **Backtracking Search with MRV + LCV** — AIMA Chapter 6.3: variable/value ordering heuristics
3. **Forward Checking with Singleton Propagation** — AIMA Chapter 6.3: constraint propagation after assignment
4. **AC-3 Arc Consistency** — AIMA Chapter 6.2: reducing domains before search
5. **Information-Theoretic Word Selection** — AIMA Chapter 3.6 (informed search): using Shannon entropy to pick the guess that maximizes expected information gain, analogous to A* using heuristics to guide search efficiently

## State Space Formulation

- **Initial state**: All positions have domain {a-z}, no constraints, full word list as candidates
- **Actions**: Pick a guess word, receive color feedback, apply constraints, propagate
- **Goal state**: All positions have domain size 1 and the assignment matches the secret word
- **Transition**: Each guess adds constraints → propagation reduces domains → candidates shrink

## Pseudocode

### Entropy-Based Selection
```
function RANK_GUESSES(candidates, all_words):
    for each word W in evaluation_set:
        for each candidate C in candidates:
            pattern = SIMULATE_FEEDBACK(W, C)
            distribution[pattern] += 1
        entropy = -sum(p * log2(p) for p in distribution)
        score = entropy + 0.1 * (W in candidates)
    return top_k words sorted by score descending
```

### Backtracking + MRV + LCV
```
function BACKTRACK(assignment, csp):
    if assignment is complete: return assignment
    var = SELECT_VARIABLE_MRV(csp)          # fewest remaining values
    for value in ORDER_VALUES_LCV(var, csp): # least constraining first
        if value is consistent with assignment:
            assignment[var] = value
            if FORWARD_CHECK(csp) succeeds:
                result = BACKTRACK(assignment, csp)
                if result != failure: return result
            remove assignment[var]
    return failure
```

### Forward Checking
```
function FORWARD_CHECK(csp):
    for each unassigned variable V:
        remove inconsistent values from domain(V)
        if domain(V) is empty: return FAILURE
        if |domain(V)| == 1: PROPAGATE_SINGLETON(V)
    return SUCCESS
```

### AC-3 Arc Consistency
```
function AC3(csp):
    queue = all arcs from must_have constraints
    while queue is not empty:
        (Xi, constraint) = queue.pop()
        if REVISE(Xi, constraint):
            if domain(Xi) is empty: return FAILURE
            for each Xk neighbor of Xi:
                queue.add((Xk, constraint))
    return SUCCESS
```

## MRV Heuristic

Pick the position with the fewest remaining letters. This causes failures (contradictions) to surface early, pruning the search tree. Combined with LCV (try letters that constrain other positions the least), this minimizes both search depth and branching factor.

## Entropy-Based Selection

For each possible guess word, simulate all feedback patterns against remaining candidates. The word whose feedback patterns are most evenly distributed (highest Shannon entropy) gives the most information on average. This is the key to solving most 5-letter words in 3-4 guesses.

## Graph Visualization

- Dark background Cytoscape graph showing the search tree
- Gray nodes = explored states, Green nodes = selected path, Red = pruned, Teal = solved
- Edges show constraints applied between states

## Setup

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

## Team

| Name | Department |
|------|-----------|
| [Name 1] | [Dept] |
| [Name 2] | [Dept] |
| [Name 3] | [Dept] |
| [Name 4] | [Dept] |
