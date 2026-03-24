"""Information-theoretic word scoring for optimal guess selection.

This is the key to solving Wordle efficiently. Instead of guessing randomly,
we compute which word gives the MAXIMUM EXPECTED INFORMATION GAIN using
Shannon entropy. A guess that splits candidates into many equally-sized
groups has high entropy — it reveals the most about the secret word.

References: Shannon (1948), AIMA Ch. 3.5-3.6 (informed search / heuristics).
"""
import math
from game.words import compute_pattern

# Precomputed high-entropy openers chosen for maximum letter coverage
_OPENERS = {
    3: "are", 4: "sale", 5: "crane", 6: "plains", 7: "strange", 8: "strained",
    9: "relations", 10: "speculator", 11: "personality", 12: "appreciation",
    13: "communicative", 14: "characteristic", 15: "representations"
}


def get_opener(length):
    """Return a precomputed high-entropy opener for the given word length.

    These words are selected for maximum letter coverage and entropy,
    giving the best average information gain on the first guess.
    """
    return _OPENERS.get(length, "crane")


def compute_pattern_distribution(guess, candidates):
    """For a given guess, simulate checking against every remaining candidate.

    Groups candidates by the resulting color pattern. This is pattern space
    simulation — a one-level lookahead similar to minimax without an adversary.
    The solver imagines every response and evaluates the outcome.

    Returns dict mapping pattern (as int) to count of candidates producing it.
    """
    distribution = {}
    for candidate in candidates:
        pat = compute_pattern(guess, candidate)
        key = _pattern_to_int(pat)
        distribution[key] = distribution.get(key, 0) + 1
    return distribution


def compute_entropy(guess, candidates):
    """Compute Shannon entropy for a guess against candidate set.

    H(guess) = -sum(p * log2(p)) for each pattern group.
    Higher entropy = more information gained on average = better guess.
    This is THE key metric for solving in 3-4 guesses instead of 5-6.
    """
    dist = compute_pattern_distribution(guess, candidates)
    total = len(candidates)
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in dist.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def compute_expected_remaining(guess, candidates):
    """Compute expected number of remaining candidates after this guess.

    E[remaining] = sum(count^2 / total) for each pattern group.
    Lower expected remaining = better guess. More practical than pure
    entropy when candidate counts are small (AIMA Ch. 16).
    """
    dist = compute_pattern_distribution(guess, candidates)
    total = len(candidates)
    if total == 0:
        return 0.0
    return sum(c * c for c in dist.values()) / total


def rank_guesses(candidates, all_words, state, top_k=10):
    """Score guess words and return the top_k ranked by score.

    Uses entropy as the primary metric with a small bonus for candidate words
    (so we might solve in one guess). Aggressively limits the evaluation set
    for performance: when candidates > 200, only scores a sample of candidates
    plus top words by unique letter coverage.

    Score = entropy + 0.1 * is_candidate. Returns list of dicts with
    word, entropy, expected_remaining, is_candidate, and score.
    """
    total = len(candidates)
    if total == 0:
        return []
    if total <= 2:
        return [{"word": w, "entropy": 0.0, "expected_remaining": 1.0,
                 "is_candidate": True, "score": 0.1} for w in candidates]

    candidate_set = set(candidates)

    if total > 200:
        eval_words = _select_eval_words(candidates, all_words)
    elif total > 50:
        # Score candidates + top 100 non-candidate words by unique letters
        non_cands = [(w, len(set(w))) for w in all_words if w not in candidate_set]
        non_cands.sort(key=lambda x: -x[1])
        extras = [w for w, _ in non_cands[:100]]
        eval_words = candidates + extras
    else:
        eval_words = all_words

    scored = []
    for guess in eval_words:
        ent = compute_entropy(guess, candidates)
        is_cand = guess in candidate_set
        score = ent + (0.1 if is_cand else 0.0)
        scored.append({
            "word": guess, "entropy": round(ent, 4),
            "expected_remaining": round(compute_expected_remaining(guess, candidates), 2),
            "is_candidate": is_cand, "score": round(score, 4)
        })

    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]


def _select_eval_words(candidates, all_words):
    """Select a sample of candidates + top non-candidate words by letter coverage.

    When candidates > 200, scoring ALL candidates is too slow. We sample up to
    150 candidates (evenly spaced) plus 50 non-candidate words with the most
    distinct letters, which tend to be the best information-gathering guesses.
    """
    candidate_set = set(candidates)
    # Sample candidates evenly if too many
    if len(candidates) > 150:
        step = len(candidates) / 150
        sampled = [candidates[int(i * step)] for i in range(150)]
    else:
        sampled = list(candidates)
    non_cands = [(w, len(set(w))) for w in all_words if w not in candidate_set]
    non_cands.sort(key=lambda x: -x[1])
    extras = [w for w, _ in non_cands[:50]]
    return sampled + extras


def _pattern_to_int(pattern):
    """Encode a pattern tuple as a single integer for fast dict bucketing.

    For 5-letter words, produces values in [0, 242] (3^5 - 1).
    Each position contributes its value * 3^position.
    """
    val = 0
    for i, p in enumerate(pattern):
        val += p * (3 ** i)
    return val
