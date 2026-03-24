/* ================================================================
   CSP Wordle Solver — app.js
   All 14 animations wired in.  Every animation respects
   @media (prefers-reduced-motion: reduce) via the `prefersMotion`
   flag checked before any JS-driven animation runs.
   ================================================================ */

let wordLen = 5, maxGuesses = 6, guessNum = 0, gameActive = false, cy = null, boardRows = 6;
let prevCandidates = 0;          // for #10 candidate count roll-down
let activeNodeId = null;         // for #7 active-node pulse
let pulseAnim = null;            // Cytoscape animation handle
let prevTraceLen = 0;            // for #9 trace slide-in stagger
let guessHistory = [];           // [{word, result}] for end-game modal
let lastTrace = [];              // full trace for end-game modal
let lastAlgoStats = [];          // accumulated algo stats per guess

function $(sel)  { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

/* Reduced-motion check */
const prefersMotion = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ----------------------------------------------------------------
   UTILITY: animateValue  (#10, #12)
   Smoothly counts a number from `start` to `end` over `duration` ms.
   Uses ease-out cubic for dramatic feel.
   ---------------------------------------------------------------- */
function animateValue(el, start, end, duration, suffix) {
    if (!prefersMotion || duration <= 0) { el.textContent = end + (suffix||''); return; }
    const range = end - start;
    const t0 = performance.now();
    function tick(now) {
        let p = Math.min((now - t0) / duration, 1);
        p = 1 - Math.pow(1 - p, 3);                     // ease-out cubic
        el.textContent = Math.round(start + range * p) + (suffix||'');
        if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

/* ----------------------------------------------------------------
   UTILITY: staggeredReveal
   Adds `animClass` to each element with increasing CSS
   animation-delay.
   ---------------------------------------------------------------- */
function staggeredReveal(elements, animClass, delayMs) {
    elements.forEach((el, i) => {
        el.style.animationDelay = (i * delayMs) + 'ms';
        el.classList.add(animClass);
    });
}

/* ================================================================
   ENTER KEY
   ================================================================ */
$('#secret-word').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') initGame();
});

/* ================================================================
   START GAME
   ================================================================ */
async function initGame() {
    const secret = $('#secret-word').value.toLowerCase().trim();
    if (secret.length < 3 || secret.length > 15) { showError('Word must be 3-15 letters'); return; }
    wordLen = secret.length;
    showError('');

    const btn = $('#btn-start');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'Loading...';

    const resp = await fetch('/start', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({secret}) });
    const data = await resp.json();

    if (!data.success) {
        showError(data.error);
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Start';
        return;
    }

    maxGuesses = data.max_guesses; guessNum = 0; gameActive = true;
    prevCandidates = data.prediction.candidates_remaining;
    prevTraceLen = 0;
    guessHistory = [];
    lastTrace = [];
    lastAlgoStats = [];

    // 1. Collapse hero
    const hero = $('#hero');
    hero.classList.add('collapsing');

    // 2. Compact input in top bar
    const topControls = $('#top-controls');
    topControls.innerHTML = `
      <div class="top-input-wrap">
        <input type="text" id="secret-word-top" value="${secret.toUpperCase()}" readonly>
        <button class="btn-start-sm" onclick="resetGame()">New game</button>
      </div>`;
    document.body.classList.add('game-started');

    // 3. Reveal game area after hero fades
    setTimeout(() => {
        hero.classList.add('hidden');
        const gw = $('#game-wrapper');
        gw.classList.remove('hidden');
        gw.classList.add('revealing');
        buildBoard(); updateDomainGrid(data.domain_grid);
        $('#start-wl').textContent = data.start_state.word_length;
        $('#start-tc').textContent = data.start_state.total_candidates;
        $('#start-dom').textContent = data.start_state.initial_domains;
        $('.state-card:last-child').classList.add('hidden');
        $('#status-line').textContent = 'Guess 0/' + maxGuesses + ' \u00b7 ' + wordLen + ' letters \u00b7 ' + data.prediction.candidates_remaining + ' candidates';
        updatePrediction(data.prediction, null);
        $('#btn-next').disabled = false;
        $('#trace-body').innerHTML = '';

        // Auto-trigger first guess after 2s so user sees the board before AI moves
        setTimeout(() => { if (gameActive && guessNum === 0) nextGuess(); }, 2000);
    }, 450);
}

/* ================================================================
   RESET GAME — animated reverse transition
   ================================================================ */
function resetGame() {
    gameActive = false;
    prevCandidates = 0; prevTraceLen = 0;
    activeNodeId = null; pulseAnim = null;
    if (cy) { cy.destroy(); cy = null; }
    guessHistory = []; lastTrace = []; lastAlgoStats = [];

    const gw = $('#game-wrapper');
    const hero = $('#hero');
    const topWrap = $('.top-input-wrap');

    // 1. Animate top-bar input out
    if (topWrap && prefersMotion) {
        topWrap.classList.add('exiting');
    }

    // 2. Animate game area out
    if (prefersMotion) {
        gw.classList.remove('revealing');
        gw.classList.add('dismissing');
    }

    // 3. After game dismisses, bring hero back
    const delay = prefersMotion ? 550 : 0;
    setTimeout(() => {
        // Clean up game wrapper
        gw.classList.add('hidden');
        gw.classList.remove('dismissing', 'revealing');
        // Reset game wrapper inline styles from animations
        gw.style.opacity = '';
        gw.style.transform = '';

        // Clear top bar
        $('#top-controls').innerHTML = '';
        document.body.classList.remove('game-started');

        // Show hero with return animation
        hero.classList.remove('collapsing', 'hidden');
        if (prefersMotion) {
            hero.classList.add('returning');
            hero.addEventListener('animationend', function handler() {
                hero.classList.remove('returning');
                hero.removeEventListener('animationend', handler);
            });
        }

        // Reset input
        $('#secret-word').value = '';
        setTimeout(() => $('#secret-word').focus(), 100);

        // Reset start button
        const btn = $('#btn-start');
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Start';
    }, delay);
}

/* ================================================================
   BUILD BOARD
   ================================================================ */
function buildBoard() {
    const board = $('#board'); board.innerHTML = '';
    // Scale cells down for longer words
    const cellSize = wordLen <= 8 ? 52 : wordLen <= 11 ? 40 : 32;
    const fontSize = wordLen <= 8 ? 20 : wordLen <= 11 ? 16 : 13;
    board.style.gridTemplateColumns = 'repeat(' + wordLen + ', ' + cellSize + 'px)';
    board.dataset.cellSize = cellSize;
    board.dataset.fontSize = fontSize;
    boardRows = maxGuesses;
    for (let r = 0; r < boardRows; r++)
        for (let c = 0; c < wordLen; c++) {
            const cell = document.createElement('div');
            cell.className = 'cell' + (r === 0 ? ' active-row' : '');
            cell.id = 'c' + r + '-' + c;
            cell.style.width = cellSize + 'px';
            cell.style.height = cellSize + 'px';
            cell.style.fontSize = fontSize + 'px';
            board.appendChild(cell);
        }
}

function addBoardRow() {
    const board = $('#board');
    const cellSize = parseInt(board.dataset.cellSize) || 52;
    const fontSize = parseInt(board.dataset.fontSize) || 20;
    const r = boardRows;
    for (let c = 0; c < wordLen; c++) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.id = 'c' + r + '-' + c;
        cell.style.width = cellSize + 'px';
        cell.style.height = cellSize + 'px';
        cell.style.fontSize = fontSize + 'px';
        board.appendChild(cell);
    }
    boardRows++;
}

/* ================================================================
   CYTOSCAPE INIT
   ================================================================ */
function initCytoscape() {
    if (cy) cy.destroy();
    const container = document.getElementById('cy');
    cy = cytoscape({ container: container, elements: [],
        style: [
            {selector:'node', style:{'label':'data(label)','text-wrap':'wrap','text-valign':'center','text-halign':'center','font-family':'monospace','font-size':'13px','padding':'14px','shape':'round-rectangle','width':function(ele){var l=ele.data('label')||''; var lines=l.split('\n'); var maxLen=Math.max(...lines.map(function(s){return s.length;})); return Math.max(100, maxLen*9+28);},'height':function(ele){var l=ele.data('label')||''; var lines=l.split('\n').length; return Math.max(40, lines*20+16);},'opacity':1}},
            {selector:'node[type="start"]',    style:{'background-color':'#1a1a1a','color':'#999','border-width':2,'border-color':'#444','font-size':'14px'}},
            {selector:'node[type="selected"]', style:{'background-color':'#0d2818','color':'#6ee7a0','border-width':2,'border-color':'#22543d','font-size':'14px','font-weight':'bold'}},
            {selector:'node[type="pruned"]',   style:{'background-color':'#2d1215','color':'#fca5a5','border-width':2,'border-color':'#7f1d1d'}},
            {selector:'node[type="solved"]',   style:{'background-color':'#0d2d2d','color':'#5eead4','border-width':2,'border-color':'#115e59','font-size':'14px','font-weight':'bold'}},
            {selector:'node[type="explored"]', style:{'background-color':'#1a1a2a','color':'#9999dd','border-width':1,'border-color':'#555','border-style':'dashed','opacity':0.8,'font-size':'11px'}},
            {selector:'edge', style:{'width':1.5,'line-color':'#444','target-arrow-color':'#555','target-arrow-shape':'triangle','curve-style':'bezier','label':'data(label)','font-size':'11px','color':'#777','font-family':'monospace','opacity':1}},
            {selector:'edge[id *= "_alt"]', style:{'line-style':'dashed','line-color':'#2a2a44','target-arrow-color':'#2a2a44','opacity':0.5}}
        ],
        layout: {name:'breadthfirst', directed:true, spacingFactor:1.8},
        userZoomingEnabled: true,
        userPanningEnabled: true
    });
}

/* ================================================================
   #13  THINKING DOTS
   ================================================================ */
function showThinking(btn) {
    btn.innerHTML = 'thinking <span class="thinking-dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>';
}
function hideThinking(btn) {
    btn.textContent = 'Next guess';
}

/* ================================================================
   NEXT GUESS  — orchestrates cell reveal → delayed UI update
   ================================================================ */
async function nextGuess() {
    if (!gameActive) return;
    const btn = $('#btn-next');
    btn.disabled = true;
    showThinking(btn);                              // #13

    const resp = await fetch('/guess', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const data = await resp.json();
    hideThinking(btn);

    if (data.error) { showError(data.error); btn.disabled = false; return; }

    // Track for end-game modal
    if (data.guess) guessHistory.push({ word: data.guess, result: data.result });
    if (data.trace) lastTrace = data.trace;
    if (data.algo_stats) lastAlgoStats.push(data.algo_stats);

    // --- #7 stop previous pulse ---
    stopPulse();

    // --- Cell reveal with stagger ---
    let cellAnimDuration = 0;
    const solved = data.solved;
    if (data.guess) {
        const CELL_STAGGER = 150;                   // #1
        for (let i = 0; i < wordLen; i++) {
            const cell = $('#c' + guessNum + '-' + i);
            if (!cell) continue;
            cell.textContent = data.guess[i].toUpperCase();
            // Apply colour AFTER half the flip so it reveals mid-animation
            if (prefersMotion) {
                cell.style.animationDelay = (i * CELL_STAGGER) + 'ms';
                cell.classList.add('flip-reveal');
                // Set colour at the midpoint of this cell's flip
                ((c, color, delay) => {
                    setTimeout(() => { c.classList.add(color); }, delay + 250);
                })(cell, data.result[i], i * CELL_STAGGER);
            } else {
                cell.classList.add(data.result[i]);
            }
        }
        cellAnimDuration = prefersMotion ? (wordLen * CELL_STAGGER + 500) : 0;

        // #3 — solved row bounce (after flip finishes)
        if (solved && prefersMotion) {
            setTimeout(() => {
                for (let i = 0; i < wordLen; i++) {
                    const c = $('#c' + guessNum + '-' + i);
                    if (c) {
                        c.style.animationDelay = (i * 80) + 'ms';
                        c.classList.add('bounce-solve');
                    }
                }
            }, cellAnimDuration);
            cellAnimDuration += wordLen * 80 + 500;
        }

        // Activate next row — add new row if needed
        guessNum++;
        if (guessNum >= boardRows) addBoardRow();
        for (let i = 0; i < wordLen; i++) {
            const nc = $('#c'+guessNum+'-'+i);
            if (nc) nc.classList.add('active-row');
        }
    }

    // --- Delay rest of UI until cell animation finishes ---
    setTimeout(() => {
        if (data.domain_grid) updateDomainGrid(data.domain_grid);   // #4 #5
        if (data.graph)       updateGraph(data.graph);               // #6 #7 #8
        if (data.trace)       updateTrace(data.trace);               // #9
        if (data.prediction)  updatePrediction(data.prediction, data.guess); // #14

        // #10 — candidate count roll-down
        const newCands = data.candidates_remaining || 0;
        const statusEl = $('#status-line');
        const guessLabel = guessNum > maxGuesses
            ? 'Guess ' + guessNum + ' (limit was ' + maxGuesses + ')'
            : 'Guess ' + guessNum + '/' + maxGuesses;
        statusEl.textContent = guessLabel + ' \u00b7 ' + wordLen + ' letters \u00b7 ';
        const countSpan = document.createElement('span');
        countSpan.id = 'cand-count';
        statusEl.appendChild(countSpan);
        const suffix = ' candidates';
        animateValue(countSpan, prevCandidates, newCands, 400, suffix);
        prevCandidates = newCands;

        if (data.algo_stats) updateAlgoStats(data.algo_stats);

        // Show exceeded warning but keep going
        if (data.exceeded && !data.solved) {
            const statusEl = $('#status-line');
            statusEl.innerHTML = '<span style="color:#991b1b">Exceeded ' + maxGuesses + ' guesses — still searching...</span> \u00b7 ';
            const countSpan2 = document.createElement('span');
            statusEl.appendChild(countSpan2);
            countSpan2.textContent = (data.candidates_remaining || 0) + ' candidates';
        }

        if (data.solved) {
            gameActive = false;
            btn.disabled = true;
            showEndState(data.end_state);           // #11 #12
            // Show summary modal after a short delay for end card to animate
            setTimeout(() => showSummaryModal(data.end_state, lastTrace), 800);
        } else if (data.failed) {
            // Only if solver ran out of candidates entirely
            gameActive = false;
            btn.disabled = true;
            showEndState(data.end_state);
            setTimeout(() => showSummaryModal(data.end_state, lastTrace), 800);
        } else {
            btn.disabled = false;
        }
    }, cellAnimDuration);
}

/* ================================================================
   #4  DOMAIN CHIP CASCADE  +  #5 GREEN LOCK RIPPLE
   ================================================================ */
function updateDomainGrid(grid) {
    const sec = $('#domain-grid'); sec.innerHTML = '';
    grid.forEach((pos, rowIdx) => {
        const row = document.createElement('div'); row.className = 'domain-row';
        row.innerHTML = '<span class="pos-label">P' + rowIdx + '</span>';
        const active = Object.values(pos).filter(v => v).length;
        let chipIdx = 0;
        for (const ch of 'abcdefghijklmnopqrstuvwxyz') {
            const chip = document.createElement('span');
            const isElim = !pos[ch];
            const isFixed = pos[ch] && active === 1;
            chip.className = 'domain-chip';
            chip.textContent = ch;

            if (prefersMotion) {
                // #4 — staggered elimination transition-delay
                chip.style.transitionDelay = (chipIdx * 30) + 'ms';
            }

            if (isElim)  chip.classList.add('eliminated');
            if (isFixed) {
                // #4 fixed bounce-in starts AFTER eliminations (~26*30=780ms)
                if (prefersMotion) {
                    chip.style.animationDelay = (26 * 30 + 50) + 'ms';
                    chip.classList.add('fixed', 'ripple');         // #5
                } else {
                    chip.classList.add('fixed');
                }
            }
            row.appendChild(chip);
            chipIdx++;
        }
        sec.appendChild(row);
    });
}

/* ================================================================
   #6  GRAPH NODE GROW-IN + EDGE DRAW
   #7  ACTIVE NODE PULSE
   #8  PRUNED NODE SHAKE
   ================================================================ */
function updateGraph(graph) {
    if (!cy) {
        initCytoscape();
        // Let Cytoscape fully initialize before adding elements
        requestAnimationFrame(() => updateGraph(graph));
        return;
    }
    try {
        cy.resize();

        const existingNodeIds = new Set(cy.nodes().map(n => n.id()));
        const existingEdgeIds = new Set(cy.edges().map(e => e.id()));
        const newNodes = graph.nodes.filter(n => !existingNodeIds.has(n.data.id));
        const newEdges = graph.edges.filter(e => !existingEdgeIds.has(e.data.id));

        if (!newNodes.length && !newEdges.length) return;

        cy.add([...newNodes, ...newEdges]);
        cy.layout({name:'breadthfirst', directed:true, spacingFactor:1.5, fit:true, padding:30}).run();
        cy.fit(undefined, 30);

        // #8 — pruned node shake
        if (prefersMotion) {
            newNodes.forEach((nd, i) => {
                if (nd.data.type === 'pruned') {
                    const n = cy.getElementById(nd.data.id);
                    if (!n.length) return;
                    const pos = n.position();
                    setTimeout(() => {
                        n.animate({ position: { x: pos.x - 3, y: pos.y } }, { duration: 50 })
                         .animate({ position: { x: pos.x + 3, y: pos.y } }, { duration: 50 })
                         .animate({ position: { x: pos.x - 3, y: pos.y } }, { duration: 50 })
                         .animate({ position: { x: pos.x + 3, y: pos.y } }, { duration: 50 })
                         .animate({ position: { x: pos.x,     y: pos.y } }, { duration: 50 });
                    }, 300 + i * 80);
                }
            });
        }

        // #7 — pulse the newest "selected" or "solved" node
        const lastNew = [...newNodes].reverse().find(n =>
            n.data.type === 'selected' || n.data.type === 'solved'
        );
        if (lastNew) startPulse(lastNew.data.id);

    } catch(e) { console.warn('Graph error:', e); }
}

/* #7 — Active node pulse */
function startPulse(nodeId) {
    stopPulse();
    activeNodeId = nodeId;
    const n = cy.getElementById(nodeId);
    if (!n.length || !prefersMotion) return;

    let iter = 0;
    function doPulse() {
        if (iter >= 4 || !activeNodeId) return;  // 2 full cycles (up+down each)
        const bw = iter % 2 === 0 ? 4 : 1;
        pulseAnim = n.animate(
            { style: { 'border-width': bw } },
            { duration: 400, complete: () => { iter++; doPulse(); } }
        );
    }
    doPulse();
}
function stopPulse() {
    if (activeNodeId && cy) {
        const n = cy.getElementById(activeNodeId);
        if (n.length) { n.stop(); n.style('border-width', 1); }
    }
    activeNodeId = null;
    pulseAnim = null;
}

/* ================================================================
   #9  TRACE LOG ROW SLIDE-IN
   ================================================================ */
function updateTrace(trace) {
    const body = $('#trace-body');
    body.innerHTML = '';
    const newCount = trace.length - prevTraceLen;
    for (let i = trace.length - 1; i >= 0; i--) {
        const t = trace[i];
        const row = document.createElement('div');
        row.className = 'trace-row';
        // Stagger only truly new rows
        const rowAge = trace.length - 1 - i;    // 0 = newest
        if (prefersMotion && rowAge < newCount) {
            row.style.animationDelay = (rowAge * 100) + 'ms';
        } else {
            row.style.animation = 'none';
            row.style.opacity = 1;
            row.style.transform = 'none';
        }
        row.innerHTML = '<span class="step mono">'+t.step+'</span><span class="desc">'+t.description+'</span><span><span class="badge '+t.status+'">'+t.status+'</span></span>';
        body.appendChild(row);
    }
    prevTraceLen = trace.length;
    // Scroll to top after animation
    if (prefersMotion && newCount > 0)
        setTimeout(() => { body.parentElement.scrollTop = 0; }, newCount * 100 + 300);
    else
        body.parentElement.scrollTop = 0;
}

/* ================================================================
   #14  PREDICTION PILL SWAP
   ================================================================ */
function updatePrediction(pred, chosen) {
    const pills = $('#pred-pills');
    const oldPills = pills.querySelectorAll('.pred-pill');
    const candidates = pred.top_candidates || [];

    function insertNew() {
        pills.innerHTML = '';
        candidates.forEach((c, i) => {
            const p = document.createElement('div');
            const isChosen = c.word === chosen;
            p.className = 'pred-pill' + (isChosen ? ' chosen' : '');
            if (prefersMotion) {
                p.style.animationDelay = (i * 60) + 'ms';
            } else {
                p.style.opacity = 1;
                p.style.transform = 'none';
            }
            p.innerHTML = '<div class="word mono">'+c.word+'</div><div class="score">'+c.score+'</div>';
            pills.appendChild(p);
        });

        const s = [];
        if (candidates.length && candidates[0].entropy !== undefined) s.push('Entropy: '+candidates[0].entropy+' bits');
        s.push('Est. '+pred.estimated_remaining_guesses+' more guesses');
        s.push('Confidence: '+(pred.confidence*100).toFixed(1)+'%');
        $('#pred-stats').textContent = s.join(' \u00b7 ');
    }

    // Fade out old pills first, then insert new
    if (oldPills.length && prefersMotion) {
        oldPills.forEach(p => p.classList.add('pill-out'));
        setTimeout(insertNew, 150);
    } else {
        insertNew();
    }
}

/* ================================================================
   ALGO STATS
   ================================================================ */
function updateAlgoStats(s) {
    if (!s) return;
    const p = [];
    if (s.entropy_of_chosen !== undefined) p.push('Entropy: '+s.entropy_of_chosen);
    if (s.ac3_arcs_revised !== undefined)  p.push('AC-3 arcs: '+s.ac3_arcs_revised);
    if (s.domains_pruned !== undefined)    p.push('Pruned: '+s.domains_pruned);
    if (s.backtrack_steps !== undefined)   p.push('Backtrack steps: '+s.backtrack_steps);
    $('#algo-stats').textContent = p.join(' \u00b7 ');
}

/* ================================================================
   #11 NARROWING BAR GROWTH  +  #12 END CARD SLIDE-UP
   ================================================================ */
function showEndState(es) {
    if (!es) return;
    const card = $('.state-card:last-child');
    card.classList.remove('hidden');
    const isSolved = es.result === 'solved';
    card.className = 'state-card ' + (isSolved ? 'solved-card' : 'failed-card');

    // #12 — slide-up reveal
    if (prefersMotion) card.classList.add('end-reveal');

    const pct = ((1 - es.total_candidates_end / es.total_candidates_start) * 100);
    card.innerHTML =
        '<div class="card-title">End State</div>' +
        '<div class="big-num end-result-text">' + (isSolved ? 'Solved' : 'Failed') + '</div>' +
        '<div class="label"><span class="end-stat" data-end="'+es.guesses_taken+'">0</span>/'+es.max_guesses+' guesses</div>' +
        '<div class="label"><span class="end-stat" data-end="'+es.total_candidates_end+'">0</span> candidates remaining</div>' +
        '<div class="narrow-bar"><div class="fill '+(isSolved?'green':'red')+'" data-pct="'+pct+'"></div></div>';

    // #12 — staggered stat count-ups
    if (prefersMotion) {
        const stats = card.querySelectorAll('.end-stat');
        stats.forEach((el, i) => {
            const endVal = parseInt(el.dataset.end, 10);
            setTimeout(() => animateValue(el, 0, endVal, 400), 300 + i * 150);
        });
    } else {
        card.querySelectorAll('.end-stat').forEach(el => {
            el.textContent = el.dataset.end;
        });
    }

    // #11 — narrowing bar width animation
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            const bar = card.querySelector('.fill');
            if (bar) bar.style.width = bar.dataset.pct + '%';
        });
    });
}

/* ================================================================
   GAME-END SUMMARY MODAL
   ================================================================ */
let modalCy = null; // Cytoscape instance for the modal graph

function showSummaryModal(es, trace) {
    if (!es) return;
    const overlay = $('#modal-overlay');
    const content = $('#modal-content');
    const isSolved = es.result === 'solved';
    const pct = ((1 - es.total_candidates_end / es.total_candidates_start) * 100).toFixed(1);

    // --- Header ---
    let html = '<div class="modal-header">';
    html += '<div class="modal-result ' + es.result + '">' + (isSolved ? 'Solved!' : 'Failed') + '</div>';
    html += '<div class="modal-secret">' + es.secret + '</div>';
    html += '<div class="modal-meta">';
    html += '<span>' + es.guesses_taken + '/' + es.max_guesses + ' guesses</span>';
    html += '<span>' + pct + '% eliminated</span>';
    html += '</div></div>';

    // --- Two-column body: left = board + trace, right = graph ---
    html += '<div class="modal-body">';

    // LEFT column
    html += '<div class="modal-left">';

    // Mini board replay
    html += '<div class="modal-board">';
    let cellDelay = 0;
    guessHistory.forEach((g) => {
        html += '<div class="modal-board-row">';
        for (let i = 0; i < g.word.length; i++) {
            const d = prefersMotion ? cellDelay * 60 : 0;
            html += '<div class="modal-board-cell ' + g.result[i] + '" style="animation-delay:' + d + 'ms">' + g.word[i] + '</div>';
            cellDelay++;
        }
        html += '</div>';
    });
    html += '</div>';

    // CSP Trace timeline
    html += '<div class="modal-divider"><span>CSP Trace Log</span></div>';
    html += '<div class="modal-trace-scroll">';
    html += '<div class="modal-trace">';
    trace.forEach((t, i) => {
        const d = prefersMotion ? i * 80 : 0;
        const statusClass = 't-' + t.status;
        html += '<div class="modal-trace-item ' + statusClass + '" style="animation-delay:' + d + 'ms">';
        html += '<span class="modal-trace-step">S' + t.step + '</span>';
        html += '<span class="modal-trace-desc">' + t.description + '</span>';
        html += '<span class="modal-trace-badge ' + t.status + '">' + t.status + '</span>';
        html += '</div>';
    });
    html += '</div></div>';
    html += '</div>'; // end modal-left

    // RIGHT column — graph
    html += '<div class="modal-right">';
    html += '<div class="modal-divider"><span>Search Tree</span></div>';
    html += '<div id="modal-cy"></div>';
    html += '</div>';

    html += '</div>'; // end modal-body

    // --- Stats footer ---
    html += '<div class="modal-stats">';
    html += '<div class="modal-stat"><div class="modal-stat-val">' + es.guesses_taken + '</div><div class="modal-stat-label">Guesses</div></div>';
    html += '<div class="modal-stat"><div class="modal-stat-val">' + pct + '%</div><div class="modal-stat-label">Eliminated</div></div>';
    const totalBt = lastAlgoStats.reduce((s, a) => s + (a.backtrack_steps || 0), 0);
    html += '<div class="modal-stat"><div class="modal-stat-val">' + totalBt + '</div><div class="modal-stat-label">Backtrack steps</div></div>';
    html += '</div>';

    // --- Play again ---
    html += '<div class="modal-actions"><button class="btn-play-again" onclick="closeModalAndReset()">Play again</button></div>';

    content.innerHTML = html;
    overlay.classList.remove('hidden');

    // Clone the main Cytoscape graph into the modal
    setTimeout(() => initModalGraph(), 150);
}

function initModalGraph() {
    if (modalCy) { modalCy.destroy(); modalCy = null; }
    const container = document.getElementById('modal-cy');
    if (!container || !cy) return;

    // Clone elements from the main graph
    const elements = cy.elements().jsons();

    modalCy = cytoscape({
        container: container,
        elements: elements,
        style: [
            {selector:'node', style:{'label':'data(label)','text-wrap':'wrap','text-valign':'center','text-halign':'center','font-family':'monospace','font-size':'12px','padding':'12px','shape':'round-rectangle','width':function(ele){var l=ele.data('label')||''; var lines=l.split('\n'); var maxLen=Math.max(...lines.map(function(s){return s.length;})); return Math.max(90, maxLen*8+24);},'height':function(ele){var l=ele.data('label')||''; var lines=l.split('\n').length; return Math.max(36, lines*18+14);}}},
            {selector:'node[type="start"]',    style:{'background-color':'#1a1a1a','color':'#999','border-width':2,'border-color':'#444'}},
            {selector:'node[type="selected"]', style:{'background-color':'#0d2818','color':'#6ee7a0','border-width':2,'border-color':'#22543d','font-weight':'bold'}},
            {selector:'node[type="pruned"]',   style:{'background-color':'#2d1215','color':'#fca5a5','border-width':2,'border-color':'#7f1d1d'}},
            {selector:'node[type="solved"]',   style:{'background-color':'#0d2d2d','color':'#5eead4','border-width':2,'border-color':'#115e59','font-weight':'bold'}},
            {selector:'node[type="explored"]', style:{'background-color':'#1a1a2a','color':'#9999dd','border-width':1,'border-color':'#555','border-style':'dashed','opacity':0.8,'font-size':'10px'}},
            {selector:'edge', style:{'width':1.5,'line-color':'#444','target-arrow-color':'#555','target-arrow-shape':'triangle','curve-style':'bezier','label':'data(label)','font-size':'10px','color':'#777','font-family':'monospace'}},
            {selector:'edge[id *= "_alt"]', style:{'line-style':'dashed','line-color':'#2a2a44','target-arrow-color':'#2a2a44','opacity':0.5}}
        ],
        layout: {name:'breadthfirst', directed:true, spacingFactor:1.2},
        userZoomingEnabled: true,
        userPanningEnabled: true,
        boxSelectionEnabled: false
    });

    modalCy.fit(undefined, 20);
}

function destroyModalCy() {
    if (modalCy) { modalCy.destroy(); modalCy = null; }
}

function closeModal(e) {
    if (e.target === $('#modal-overlay')) {
        const overlay = $('#modal-overlay');
        if (prefersMotion) {
            overlay.style.animation = 'modalBgIn 250ms ease reverse forwards';
            $('#modal-card').style.animation = 'modalCardIn 250ms ease reverse forwards';
            setTimeout(() => {
                destroyModalCy();
                overlay.classList.add('hidden');
                overlay.style.animation = '';
                $('#modal-card').style.animation = '';
            }, 260);
        } else {
            destroyModalCy();
            overlay.classList.add('hidden');
        }
    }
}

function closeModalAndReset() {
    destroyModalCy();
    const overlay = $('#modal-overlay');
    if (prefersMotion) {
        overlay.style.animation = 'modalBgIn 250ms ease reverse forwards';
        const card = $('#modal-card');
        card.style.animation = 'modalCardIn 250ms ease reverse forwards';
        setTimeout(() => {
            overlay.classList.add('hidden');
            overlay.style.animation = '';
            card.style.animation = '';
            resetGame();
        }, 260);
    } else {
        overlay.classList.add('hidden');
        resetGame();
    }
}

/* ================================================================
   ERROR
   ================================================================ */
function showError(msg) {
    const el = $('#error-msg');
    if (el) el.textContent = msg;
}

/* ================================================================
   MINIMALIST CAROUSEL SCROLL & INDICATORS
   ================================================================ */
/* ================================================================
   FADE CAROUSEL — AI Concepts
   ================================================================ */
var _carouselIdx = 0;
var _carouselAnimating = false;

function initCarousel() {
    var container = $('#concepts-carousel');
    var indicatorsWrap = $('#carousel-indicators');
    if (!container || !indicatorsWrap) return;

    var slides = container.querySelectorAll('.fade-slide');

    // Generate indicator dots
    for (var i = 0; i < slides.length; i++) {
        (function(idx) {
            var dot = document.createElement('div');
            dot.className = 'carousel-dot' + (idx === 0 ? ' active' : '');
            dot.onclick = function() { goToSlide(idx); };
            indicatorsWrap.appendChild(dot);
        })(i);
    }

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        // Only respond if carousel is in viewport
        var rect = container.getBoundingClientRect();
        if (rect.top > window.innerHeight || rect.bottom < 0) return;
        if (e.key === 'ArrowLeft') fadeCarousel(-1);
        if (e.key === 'ArrowRight') fadeCarousel(1);
    });
}

function goToSlide(target) {
    if (_carouselAnimating) return;
    var container = $('#concepts-carousel');
    if (!container) return;
    var slides = container.querySelectorAll('.fade-slide');
    var total = slides.length;
    if (target === _carouselIdx || target < 0 || target >= total) return;

    var dir = target > _carouselIdx ? 1 : -1;
    _carouselAnimating = true;

    var current = slides[_carouselIdx];
    var next = slides[target];

    // Exit current
    current.classList.remove('active');
    current.classList.add(dir > 0 ? 'exit-left' : 'exit-right');

    // Prepare next
    next.style.transform = dir > 0 ? 'translateX(30px)' : 'translateX(-30px)';
    next.style.opacity = '0';
    next.classList.remove('exit-left', 'exit-right');

    // Force reflow
    void next.offsetWidth;

    // Animate in
    next.classList.add('active');
    next.style.transform = '';
    next.style.opacity = '';

    _carouselIdx = target;
    updateCarouselUI(total);

    setTimeout(function() {
        current.classList.remove('exit-left', 'exit-right');
        _carouselAnimating = false;
    }, 500);
}

function fadeCarousel(dir) {
    var container = $('#concepts-carousel');
    if (!container) return;
    var total = container.querySelectorAll('.fade-slide').length;
    var target = _carouselIdx + dir;
    if (target < 0) target = total - 1;
    if (target >= total) target = 0;
    goToSlide(target);
}

function updateCarouselUI(total) {
    // Update counter
    var counter = $('#carousel-counter');
    if (counter) {
        var num = String(_carouselIdx + 1).padStart(2, '0');
        counter.textContent = num + ' / ' + String(total).padStart(2, '0');
    }
    // Update dots
    var dots = document.querySelectorAll('#carousel-indicators .carousel-dot');
    dots.forEach(function(dot, i) {
        if (i === _carouselIdx) dot.classList.add('active');
        else dot.classList.remove('active');
    });
}

initCarousel();

/* ================================================================
   WORD MARQUEE BACKGROUND
   ================================================================ */
(async function initMarquee() {
    const container = document.getElementById('word-marquee');
    if (!container) return;

    // Fallback words if API fails
    const fallback = [
        'crane','brain','apple','shift','globe','plane','trick','storm','flame','grape',
        'slice','dream','frost','light','stone','quest','blaze','charm','drift','eagle',
        'fable','ghost','haven','ivory','jewel','knack','lunar','marsh','noble','ocean',
        'prism','quilt','raven','solar','tiger','ultra','vivid','wager','xenon','yield',
        'zone','bold','calm','dare','ease','fury','glow','haze','isle','jazz',
        'abstract','brighten','creature','darkness','electron','friendly',
        'generous','harmonic','illusion','junction','keyboard','language',
        'magnetic','navigate','obstacle','paradigm','quantity','rational'
    ];

    let words;
    try {
        const resp = await fetch('/word-samples');
        const data = await resp.json();
        words = data.words && data.words.length > 20 ? data.words : fallback;
    } catch(e) { words = fallback; }

    const ROWS = 10;
    const wordsPerRow = 16;

    for (let r = 0; r < ROWS; r++) {
        const row = document.createElement('div');
        row.className = 'marquee-row ' + (r % 2 === 0 ? 'ltr' : 'rtl');

        // Random speed between 25-60s
        const speed = 25 + Math.random() * 35;
        row.style.animationDuration = speed + 's';

        // Build two copies for seamless loop
        let html = '';
        for (let copy = 0; copy < 2; copy++) {
            for (let i = 0; i < wordsPerRow; i++) {
                const w = words[Math.floor(Math.random() * words.length)];
                // Randomly assign color class
                const rnd = Math.random();
                const cls = rnd < 0.08 ? ' mw-green' : rnd < 0.14 ? ' mw-yellow' : '';
                html += '<span class="marquee-word' + cls + '">' + w + '</span>';
            }
        }
        row.innerHTML = html;
        container.appendChild(row);
    }
})();

/* ================================================================
   RANDOM WORD PICKER
   ================================================================ */
async function pickRandomWord() {
    const btn = document.getElementById('btn-random');
    const input = document.getElementById('secret-word');
    if (!btn || !input) return;

    // Dice spin animation
    btn.style.pointerEvents = 'none';
    btn.querySelector('svg').style.animation = 'diceRoll 0.4s ease';

    try {
        const resp = await fetch('/random-word');
        const data = await resp.json();
        const word = data.word.toUpperCase();

        // Clear and typewriter effect
        input.value = '';
        input.classList.add('typing');
        for (let i = 0; i < word.length; i++) {
            await new Promise(r => setTimeout(r, 60 + Math.random() * 40));
            input.value += word[i];
        }
        input.classList.remove('typing');

        // Brief flash on the input
        input.style.transition = 'box-shadow 0.3s';
        input.parentElement.style.boxShadow = '0 0 0 4px rgba(26,92,42,0.15)';
        setTimeout(() => { input.parentElement.style.boxShadow = ''; }, 600);

    } catch(e) {
        // Offline fallback — pick from a small set
        const fallbacks = ['crane','brain','ghost','flame','prism','quest','blaze','tiger'];
        const word = fallbacks[Math.floor(Math.random() * fallbacks.length)].toUpperCase();
        input.value = word;
    }

    btn.style.pointerEvents = '';
    btn.querySelector('svg').style.animation = '';
}
