"""Word list management and guess checking for Wordle.

Loads words from NLTK corpus, checks guesses with correct duplicate-letter
handling, and filters candidate words against CSP domain constraints.
"""
import os
import nltk

# Vercel serverless: filesystem is read-only except /tmp
nltk.data.path.insert(0, os.path.join('/tmp', 'nltk_data'))

_CACHE = {}


def get_word_list(length):
    """Load words of exact length from NLTK corpus, cached per length.

    Downloads the NLTK words corpus quietly on first run. Returns only
    lowercase alphabetic words of the requested length.
    """
    if length in _CACHE:
        return _CACHE[length]
    nltk.download('words', quiet=True, download_dir=os.path.join('/tmp', 'nltk_data'))
    from nltk.corpus import words
    result = sorted({
        w.lower() for w in words.words()
        if len(w) == length and w.isalpha() and w.islower()
    })
    _CACHE[length] = result
    return result


def check_guess(guess, secret):
    """Return list of color strings for each position: 'green', 'yellow', or 'grey'.

    Uses two-pass duplicate handling: greens are assigned first to consume
    exact matches, then yellows consume remaining letter counts. This ensures
    duplicate letters are scored correctly (e.g., guessing 'speed' against
    'spree' gives S=green, P=green, E=yellow, E=grey, D=grey).
    """
    n = len(guess)
    result = ['grey'] * n
    secret_counts = {}
    # Pass 1: mark greens
    for i in range(n):
        if guess[i] == secret[i]:
            result[i] = 'green'
        else:
            secret_counts[secret[i]] = secret_counts.get(secret[i], 0) + 1
    # Pass 2: mark yellows from remaining counts
    for i in range(n):
        if result[i] == 'grey' and guess[i] in secret_counts:
            if secret_counts[guess[i]] > 0:
                result[i] = 'yellow'
                secret_counts[guess[i]] -= 1
    return result


_PATTERN_CACHE = {}


def compute_pattern(guess, secret):
    """Return pattern as tuple of ints: 2=green, 1=yellow, 0=grey.

    Internal numeric representation used by the entropy module for fast
    pattern bucketing. Same duplicate-handling logic as check_guess.
    Results are cached since the same (guess, secret) pair is often evaluated
    multiple times across ranking and prediction calls.
    """
    key = (guess, secret)
    cached = _PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    n = len(guess)
    pattern = [0] * n
    secret_counts = {}
    for i in range(n):
        if guess[i] == secret[i]:
            pattern[i] = 2
        else:
            secret_counts[secret[i]] = secret_counts.get(secret[i], 0) + 1
    for i in range(n):
        if pattern[i] == 0 and guess[i] in secret_counts:
            if secret_counts[guess[i]] > 0:
                pattern[i] = 1
                secret_counts[guess[i]] -= 1
    result = tuple(pattern)
    if len(_PATTERN_CACHE) < 500000:
        _PATTERN_CACHE[key] = result
    return result


def filter_candidates(word_list, state):
    """Keep only words where every letter at every position is in that position's domain.

    This is domain-based filtering: a word is valid only if each of its letters
    belongs to the current domain set for that position. Words with letters
    pruned from any position's domain are eliminated without being explored.
    """
    filtered = []
    for word in word_list:
        valid = True
        for i, ch in enumerate(word):
            if ch not in state.domains[i]:
                valid = False
                break
        if not valid:
            continue
        # Check must_have constraints
        for letter, min_count in state.must_have.items():
            if word.count(letter) < min_count:
                valid = False
                break
        # Check excluded letters (only if not in must_have)
        if valid:
            for ch in word:
                if ch in state.excluded and ch not in state.must_have:
                    valid = False
                    break
        if valid:
            filtered.append(word)
    return filtered
