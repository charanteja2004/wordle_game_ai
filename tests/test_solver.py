"""Tests for the CSP Wordle Solver.

Validates core algorithms: guess checking with duplicate handling,
constraint propagation, AC-3, forward checking, entropy scoring,
and full end-to-end solving.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from game.words import check_guess, compute_pattern, get_word_list
from algo.csp import CSPState, apply_constraints
from algo.ac3 import ac3
from algo.forward_check import forward_check
from algo.entropy import compute_entropy, compute_pattern_distribution
from algo.solver import initialize, next_guess, process_result


def test_check_guess_basic():
    """check_guess: exact match returns all green."""
    result = check_guess("crane", "crane")
    assert result == ["green", "green", "green", "green", "green"]


def test_check_guess_duplicates():
    """check_guess: duplicate letters scored correctly.

    'apple' vs 'papal': a=yellow, p=green, p=yellow, l=yellow, e=grey
    - a: not at pos 0 but in 'papal' -> yellow
    - p: matches pos 1 -> green
    - p: pos 2, 'papal' has p at 0 and 2, pos 1 already green-matched -> yellow
    - l: in 'papal' at pos 4 -> yellow  (wait, 'papal' has no l... let me check)
    Actually 'papal' = p,a,p,a,l. 'apple' = a,p,p,l,e.
    - a(0) vs p(0): not match. a is in papal at pos 1,3 -> yellow
    - p(1) vs a(1): not match. p is in papal at pos 0,2 -> yellow
    - p(2) vs p(2): match -> green
    - l(3) vs a(3): not match. l is in papal at pos 4 -> yellow
    - e(4) vs l(4): not match. e not in papal -> grey
    """
    result = check_guess("apple", "papal")
    assert result[2] == "green"  # p matches at position 2
    assert result[4] == "grey"   # e not in 'papal'
    # a is in papal, so position 0 should be yellow
    assert result[0] == "yellow"


def test_check_guess_no_match():
    """check_guess: completely non-overlapping letters return all grey."""
    result = check_guess("crane", "light")
    # c,r,a,n,e vs l,i,g,h,t — no overlap
    assert all(r == "grey" for r in result)


def test_constraint_application_green():
    """Green constraint fixes domain to exactly 1 letter at that position."""
    state = CSPState.initial(5)
    result = ["green", "grey", "grey", "grey", "grey"]
    new_state = apply_constraints(state, "crane", result)
    assert new_state.domains[0] == {"c"}
    assert new_state.assignment[0] == "c"


def test_ac3_reduces_domains():
    """AC-3 prunes impossible values when must_have constraints force positions."""
    state = CSPState.initial(5)
    # Simulate: we know 'a' must appear, and only position 2 can hold it
    state.must_have = {"a": 1}
    # Remove 'a' from all positions except position 2
    for i in range(5):
        if i != 2:
            state.domains[i].discard("a")
    new_state, consistent, log = ac3(state)
    assert consistent
    # Position 2 should be forced to 'a' since it's the only position
    assert new_state.domains[2] == {"a"}


def test_forward_check_detects_empty_domain():
    """Forward check returns inconsistent when a domain is emptied."""
    state = CSPState.initial(5)
    # Empty position 0's domain artificially
    state.domains[0] = set()
    _, consistent, _ = forward_check(state)
    assert not consistent


def test_entropy_scoring():
    """Word with more distinct feedback patterns scores higher entropy."""
    candidates = ["crane", "crate", "trace", "grace", "brace",
                   "space", "place", "glare", "stare", "share"]
    # A word that creates many different patterns should have higher entropy
    ent_crane = compute_entropy("crane", candidates)
    # A single-letter word repeated would create fewer patterns
    ent_aaaaa = compute_entropy("aaaaa", candidates)
    assert ent_crane > ent_aaaaa


def test_full_solve():
    """Integration test: solver finds 'crane' within max guesses."""
    secret = "crane"
    solver = initialize(5)
    max_g = 6
    solved = False
    for turn in range(max_g):
        guess_word, prediction, stats = next_guess(solver)
        if guess_word is None:
            break
        result = check_guess(guess_word, secret)
        if all(r == "green" for r in result):
            solved = True
            break
        solver = process_result(solver, guess_word, result)
    assert solved, f"Failed to solve 'crane' in {max_g} guesses"
