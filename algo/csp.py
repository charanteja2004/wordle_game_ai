"""Core CSP data structures and constraint logic for Wordle.

Models Wordle as a Constraint Satisfaction Problem where:
- Variables = letter positions (0 to word_length-1)
- Domains = set of letters still possible at each position (starts as a-z)
- Constraints = rules derived from green/yellow/grey feedback
"""
from dataclasses import dataclass, field
import string


@dataclass
class Constraint:
    """A single constraint from guess feedback.

    In CSP theory, constraints restrict which values variables can take.
    Each Wordle color feedback creates a constraint that prunes the search space.
    """
    type: str        # 'green', 'yellow', or 'grey'
    letter: str      # the guessed character
    position: int    # position in the word (0-indexed)
    guess_word: str  # the full guess word that generated this constraint


@dataclass
class CSPState:
    """Complete state of the CSP at any point during solving.

    Holds the current domains for each variable (position), all accumulated
    constraints, fixed assignments, letter requirements, and exclusions.
    """
    word_len: int
    domains: list = field(default_factory=list)       # list of set[str]
    constraints: list = field(default_factory=list)    # list of Constraint
    assignment: dict = field(default_factory=dict)     # pos -> letter
    must_have: dict = field(default_factory=dict)      # letter -> min count
    excluded: set = field(default_factory=set)         # globally excluded letters

    @staticmethod
    def initial(word_len):
        """Create initial state with full domains (all 26 letters per position)."""
        all_letters = set(string.ascii_lowercase)
        return CSPState(
            word_len=word_len,
            domains=[set(all_letters) for _ in range(word_len)],
            constraints=[], assignment={}, must_have={}, excluded=set()
        )


def apply_constraints(state, guess, result):
    """Apply feedback constraints from a guess to the CSP state.

    Implements constraint propagation: each color feedback actively shrinks
    domains rather than waiting for brute-force checking. Green fixes a letter,
    yellow restricts position but ensures presence, grey eliminates globally
    (unless the letter appears as green/yellow elsewhere in the same guess).
    """
    domains = [set(d) for d in state.domains]
    assignment = dict(state.assignment)
    must_have = dict(state.must_have)
    excluded = set(state.excluded)
    constraints = list(state.constraints)
    n = state.word_len

    green_letters = set()
    yellow_letters = set()

    # Pass 1: Greens — fix letter at position, remove from other positions
    for i in range(n):
        if result[i] == 'green':
            domains[i] = {guess[i]}
            assignment[i] = guess[i]
            green_letters.add(guess[i])
            constraints.append(Constraint('green', guess[i], i, guess))

    # Pass 2: Yellows — remove from this position, ensure elsewhere
    for i in range(n):
        if result[i] == 'yellow':
            domains[i].discard(guess[i])
            yellow_letters.add(guess[i])
            constraints.append(Constraint('yellow', guess[i], i, guess))

    # Compute minimum counts from this guess
    for letter in set(guess):
        count = sum(1 for i in range(n)
                     if guess[i] == letter and result[i] in ('green', 'yellow'))
        if count > 0:
            must_have[letter] = max(must_have.get(letter, 0), count)

    # Pass 3: Greys — remove globally unless green/yellow in same guess
    for i in range(n):
        if result[i] == 'grey':
            c = guess[i]
            if c not in green_letters and c not in yellow_letters:
                excluded.add(c)
                for d in domains:
                    d.discard(c)
            else:
                domains[i].discard(c)
            constraints.append(Constraint('grey', c, i, guess))

    # Singleton propagation — if domain has 1 value, fix it
    _propagate_singletons(domains, assignment)

    return CSPState(n, domains, constraints, assignment, must_have, excluded)


def _propagate_singletons(domains, assignment):
    """Fix positions with single remaining domain value.

    When a domain is reduced to exactly 1 letter, treat it as assigned.
    Note: we do NOT remove singletons from other positions because Wordle
    allows duplicate letters (e.g., 'speed' has two e's).
    """
    for i, d in enumerate(domains):
        if len(d) == 1 and i not in assignment:
            assignment[i] = next(iter(d))


def get_domain_grid(state):
    """Return list of dicts (one per position), each mapping a-z to bool.

    Used by the frontend to render the domain visualization grid showing
    which letters are still possible at each position.
    """
    grid = []
    for d in state.domains:
        grid.append({ch: (ch in d) for ch in string.ascii_lowercase})
    return grid


def is_consistent(word, state):
    """Check if a word is consistent with all current domains and constraints.

    A word is consistent if every letter at every position belongs to that
    position's current domain set.
    """
    if len(word) != state.word_len:
        return False
    for i, ch in enumerate(word):
        if ch not in state.domains[i]:
            return False
    for letter, min_count in state.must_have.items():
        if word.count(letter) < min_count:
            return False
    return True
