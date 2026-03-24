"""Flask web application for the CSP Wordle Solver.

Provides REST endpoints for the frontend to start games and request AI guesses.
State is stored in Flask session using a replay strategy: only guesses and
results are persisted, and the full solver state is rebuilt on each request.
This keeps session payload tiny (< 1KB) and avoids cookie size limits.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import random
from flask import Flask, render_template, request, jsonify, session
from algo.solver import initialize, next_guess, process_result, serialize_state, deserialize_state
from algo.csp import get_domain_grid
from game.words import get_word_list, check_guess

_root = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(_root, 'templates'),
            static_folder=os.path.join(_root, 'static'))
app.secret_key = 'csp-wordle-secret'

MIN_LEN = 3
MAX_LEN = 15


def max_guesses_for(length):
    """Recommended guess limit: length + 2, minimum 5."""
    return max(5, length + 2)


@app.route('/')
def index():
    """Render the main game page."""
    return render_template('index.html')


@app.route('/random-word')
def random_word():
    """Return a random word of a random length (4-8)."""
    length = random.choice(list(range(MIN_LEN, MAX_LEN + 1)))
    words = get_word_list(length)
    if not words:
        length = 5
        words = get_word_list(5)
    word = random.choice(words)
    return jsonify({"word": word, "length": length})


@app.route('/word-samples')
def word_samples():
    """Return sample words for the background marquee."""
    samples = []
    for length in range(MIN_LEN, MAX_LEN + 1):
        words = get_word_list(length)
        samples.extend(random.sample(words, min(30, len(words))))
    random.shuffle(samples)
    return jsonify({"words": samples})


@app.route('/start', methods=['POST'])
def start():
    """Start a new game with a secret word.

    Validates the secret word, initializes the solver, and returns
    initial state including domain grid and predictions.
    """
    data = request.get_json()
    secret = data.get('secret', '').lower().strip()
    length = len(secret)

    if length < MIN_LEN or length > MAX_LEN:
        return jsonify({"success": False, "error": f"Word must be {MIN_LEN}-{MAX_LEN} letters"})
    if not secret.isalpha():
        return jsonify({"success": False, "error": "Word must contain only letters"})

    words = get_word_list(length)
    if secret not in words:
        return jsonify({"success": False, "error": "Word not found in dictionary"})

    solver = initialize(length)
    session['secret'] = secret
    session['state'] = serialize_state(solver)

    return jsonify({
        "success": True, "word_length": length,
        "max_guesses": max_guesses_for(length),
        "domain_grid": get_domain_grid(solver.csp),
        "prediction": _build_initial_prediction(solver),
        "start_state": {
            "word_length": length, "total_candidates": len(solver.candidates),
            "initial_domains": f"26 x {length}"
        }
    })


@app.route('/guess', methods=['POST'])
def guess():
    """Run one AI guess cycle: pick word, check against secret, update state."""
    if 'secret' not in session or 'state' not in session:
        return jsonify({"error": "No active game. Call /start first."}), 400

    secret = session['secret']
    length = len(secret)
    max_g = max_guesses_for(length)

    solver = deserialize_state(session['state'])
    guess_word, prediction, algo_stats = next_guess(solver)

    if guess_word is None:
        session.pop('state', None)
        session.pop('secret', None)
        return jsonify({
            "guess": None, "result": [], "solved": False, "failed": True,
            "domain_grid": get_domain_grid(solver.csp),
            "candidates_remaining": 0, "trace": solver.trace,
            "graph": {"nodes": solver.graph_nodes, "edges": solver.graph_edges},
            "prediction": prediction, "algo_stats": algo_stats,
            "domain_sizes": [len(d) for d in solver.csp.domains],
            "end_state": {"secret": secret, "guesses_taken": len(solver.guesses),
                          "max_guesses": max_g, "result": "failed",
                          "total_candidates_start": solver.total_start,
                          "total_candidates_end": 0}
        })

    result = check_guess(guess_word, secret)
    solved = all(r == 'green' for r in result)
    solver = process_result(solver, guess_word, result)
    exceeded = not solved and len(solver.guesses) >= max_g

    session['state'] = serialize_state(solver)

    end_state = None
    if solved:
        session.pop('state', None)
        session.pop('secret', None)
        end_state = {
            "secret": secret, "guesses_taken": len(solver.guesses),
            "max_guesses": max_g, "result": "solved",
            "total_candidates_start": solver.total_start,
            "total_candidates_end": len(solver.candidates)
        }
        solver.graph_nodes.append({
            "data": {"id": "nSolved", "label": f"Solved!\n{guess_word}",
                     "type": "solved", "candidates": 1}
        })
        solver.graph_edges.append({
            "data": {"id": f"e{solver.step}-solved",
                     "source": f"n{solver.step}",
                     "target": "nSolved", "label": "\u2713"}
        })

    return jsonify({
        "guess": guess_word, "result": result, "solved": solved,
        "failed": False, "exceeded": exceeded,
        "domain_grid": get_domain_grid(solver.csp),
        "domain_sizes": [len(d) for d in solver.csp.domains],
        "candidates_remaining": len(solver.candidates),
        "trace": solver.trace,
        "graph": {"nodes": solver.graph_nodes, "edges": solver.graph_edges},
        "prediction": prediction, "algo_stats": algo_stats,
        "end_state": end_state
    })


def _build_initial_prediction(solver):
    """Build prediction data for the initial state before any guesses."""
    n = len(solver.candidates)
    return {
        "top_candidates": [], "candidates_remaining": n,
        "domain_sizes": [26] * solver.word_len,
        "elimination_rate": 0, "estimated_remaining_guesses": 6,
        "confidence": round(1 / n, 6) if n > 0 else 0
    }


if __name__ == '__main__':
    app.run(debug=True, port=5000)
