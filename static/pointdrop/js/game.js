// ── State ──────────────────────────────────────────────────────────────────────

const params = new URLSearchParams(window.location.search);
const SESSION_ID = params.get('session');
const PLAYER_NAME = params.get('name');

let ws = null;
let playerId = null;
let totalScore = 0;
let currentChoices = [];
let questionStartTime = null;
let answered = false;
let selectedChoice = null;
let timeSeconds = 10;
let players = {};
let reconnectAttempts = 0;
const MAX_RECONNECT = 5;
let gameFinished = false;

// ── Screens ───────────────────────────────────────────────────────────────────

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

// ── Init ──────────────────────────────────────────────────────────────────────

if (!SESSION_ID || !PLAYER_NAME) {
    window.location.href = '/';
} else {
    document.getElementById('player-name-display').textContent = PLAYER_NAME;
    showScreen('screen-waiting');
    connect();
}

function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/student/${SESSION_ID}`);

    ws.onopen = () => {
        reconnectAttempts = 0;
        ws.send(JSON.stringify({ type: 'player_join', name: PLAYER_NAME }));
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = (event) => {
        console.log('WebSocket closed', event.code, event.reason);
        if (!gameFinished && reconnectAttempts < MAX_RECONNECT) {
            reconnectAttempts++;
            const delay = Math.min(1000 * reconnectAttempts, 5000);
            console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`);
            setTimeout(connect, delay);
        } else if (!gameFinished) {
            showDisconnected();
        }
    };

    ws.onerror = (err) => {
        console.error('WebSocket error', err);
    };
}

function showDisconnected() {
    const el = document.getElementById('q-text');
    if (el) el.textContent = 'Connection lost. Please refresh the page.';
}

// ── Message Handler ───────────────────────────────────────────────────────────

function handleMessage(msg) {
    switch (msg.type) {
        case 'join_confirmed':
            playerId = msg.player_id;
            break;

        case 'player_joined':
            players[msg.player_id] = msg.name;
            document.getElementById('player-count').textContent = `${msg.player_count} players joined`;
            updatePlayerList();
            break;

        case 'player_left':
            delete players[msg.player_id];
            document.getElementById('player-count').textContent = `${msg.player_count} players joined`;
            updatePlayerList();
            break;

        case 'game_start':
            // Stay on waiting until first question
            break;

        case 'question_start':
            showQuestion(msg);
            break;

        case 'points_update':
            updatePoints(msg);
            break;

        case 'choice_eliminated':
            eliminateChoice(msg);
            break;

        case 'answer_confirmed':
            onAnswerConfirmed(msg);
            break;

        case 'question_end':
            showQuestionResult(msg);
            break;

        case 'game_end':
            showFinalResults(msg);
            break;

        case 'error':
            console.warn('Server error:', msg.message);
            if (msg.message === 'time_expired') {
                answered = true;
                const btns = document.querySelectorAll('.choice-btn');
                btns.forEach(btn => btn.classList.add('disabled'));
            }
            break;
    }
}

// ── Waiting Screen ────────────────────────────────────────────────────────────

function updatePlayerList() {
    const names = Object.values(players);
    const display = names.length > 8
        ? names.slice(0, 8).join(', ') + `, +${names.length - 8} more`
        : names.join(', ');
    document.getElementById('player-list').textContent = display;
}

// ── Question Screen ───────────────────────────────────────────────────────────

function showQuestion(msg) {
    answered = false;
    selectedChoice = null;
    currentChoices = msg.choices;
    timeSeconds = msg.time_seconds;
    questionStartTime = Date.now();

    document.getElementById('q-progress').textContent = `Question ${msg.index + 1} of ${msg.total}`;
    document.getElementById('q-text').textContent = msg.text || '';
    document.getElementById('q-timer').textContent = `${timeSeconds}s`;
    document.getElementById('q-points').textContent = `${msg.max_points} pts`;
    document.getElementById('timer-bar').style.width = '100%';
    document.getElementById('locked-msg').classList.add('hidden');

    // Image
    const imgContainer = document.getElementById('q-image-container');
    const img = document.getElementById('q-image');
    if (msg.image_url) {
        img.src = msg.image_url;
        imgContainer.classList.remove('hidden');
    } else {
        imgContainer.classList.add('hidden');
    }

    // Build choice buttons
    const grid = document.getElementById('choices-grid');
    grid.innerHTML = '';
    const colorClasses = ['choice-a', 'choice-b', 'choice-c', 'choice-d'];
    msg.choices.forEach((choice, i) => {
        const btn = document.createElement('button');
        btn.className = `choice-btn ${colorClasses[i]} animate-slide-in`;
        btn.textContent = choice;
        btn.dataset.choice = choice;
        btn.style.animationDelay = `${i * 0.05}s`;
        btn.onclick = () => submitAnswer(choice);
        grid.appendChild(btn);
    });

    showScreen('screen-question');
}

function updatePoints(msg) {
    const remaining = msg.time_remaining_ms;
    const totalMs = timeSeconds * 1000;
    const pct = Math.max(0, (remaining / totalMs) * 100);
    const secs = Math.ceil(remaining / 1000);

    document.getElementById('q-timer').textContent = `${secs}s`;
    document.getElementById('q-points').textContent = `${msg.current_points} pts`;
    document.getElementById('timer-bar').style.width = `${pct}%`;

    // Color transitions
    const bar = document.getElementById('timer-bar');
    if (pct < 33) {
        bar.className = 'h-full bg-gradient-to-r from-red-500 to-red-600 rounded-full transition-all duration-100';
    } else if (pct < 66) {
        bar.className = 'h-full bg-gradient-to-r from-amber-500 to-amber-600 rounded-full transition-all duration-100';
    }
}

function eliminateChoice(msg) {
    const btns = document.querySelectorAll('.choice-btn');
    btns.forEach(btn => {
        if (btn.dataset.choice === msg.choice) {
            btn.classList.add('eliminated');
            btn.classList.add('animate-shake');
        }
    });
}

function submitAnswer(choice) {
    if (answered) return;
    answered = true;
    selectedChoice = choice;

    const elapsedMs = Date.now() - questionStartTime;

    ws.send(JSON.stringify({
        type: 'submit_answer',
        choice: choice,
        elapsed_ms: elapsedMs,
    }));

    // Visual feedback
    const btns = document.querySelectorAll('.choice-btn');
    btns.forEach(btn => {
        if (btn.dataset.choice === choice) {
            btn.classList.add('selected');
        }
        btn.classList.add('locked');
    });
}

function onAnswerConfirmed(msg) {
    document.getElementById('locked-msg').classList.remove('hidden');
}

// ── Question Result Screen ────────────────────────────────────────────────────

function showQuestionResult(msg) {
    const myResult = msg.player_scores.find(p => p.player_id === playerId);
    const isCorrect = myResult ? myResult.is_correct : false;
    const pointsEarned = myResult ? myResult.points_earned : 0;

    if (myResult) {
        totalScore = myResult.total_score;
    }

    // Find rank
    const rank = msg.player_scores.findIndex(p => p.player_id === playerId) + 1;
    const totalPlayers = msg.total_players;

    // Progress
    const progressEl = document.getElementById('q-progress-result');
    const qProgress = document.getElementById('q-progress');
    progressEl.textContent = qProgress ? qProgress.textContent : '';

    // Banner
    const banner = document.getElementById('result-banner');
    if (!selectedChoice && !myResult) {
        banner.textContent = 'NO ANSWER';
        banner.className = 'text-4xl font-bold py-4 text-slate-400';
    } else if (isCorrect) {
        banner.textContent = 'CORRECT!';
        banner.className = 'text-4xl font-bold py-4 text-emerald-400';
    } else {
        banner.textContent = 'INCORRECT';
        banner.className = 'text-4xl font-bold py-4 text-red-400';
    }

    // Points
    const ptsEl = document.getElementById('result-points');
    ptsEl.textContent = `+${pointsEarned} points`;
    ptsEl.className = pointsEarned > 0 ? 'text-2xl text-emerald-300' : 'text-2xl text-slate-400';

    // Show choices with correct highlighted
    const choicesDiv = document.getElementById('result-choices');
    choicesDiv.innerHTML = '';
    currentChoices.forEach(choice => {
        const div = document.createElement('div');
        div.textContent = choice;

        if (choice === msg.correct_choice) {
            div.className = 'result-choice result-correct';
            if (choice === selectedChoice) {
                div.textContent += ' ✓';
            }
        } else if (choice === selectedChoice) {
            div.className = 'result-choice result-wrong-selected';
            div.textContent += ' ✗';
        } else {
            div.className = 'result-choice result-neutral';
        }
        choicesDiv.appendChild(div);
    });

    // Score & Rank
    document.getElementById('result-total-score').textContent = `${totalScore.toLocaleString()} pts`;
    document.getElementById('result-rank').textContent = rank > 0 ? `${ordinal(rank)} / ${totalPlayers}` : '-';

    showScreen('screen-result');
}

// ── Final Results Screen ──────────────────────────────────────────────────────

function showFinalResults(msg) {
    const myRank = msg.final_rankings.find(r => r.player_id === playerId);

    document.getElementById('final-score').textContent = myRank
        ? `${myRank.total_score.toLocaleString()} pts`
        : '0 pts';

    const rankNum = myRank ? myRank.rank : '-';
    const rankEl = document.getElementById('final-rank');
    if (rankNum <= 3 && rankNum >= 1) {
        const medals = ['', '🥇 1st Place 🥇', '🥈 2nd Place 🥈', '🥉 3rd Place 🥉'];
        rankEl.textContent = medals[rankNum];
        rankEl.className = 'text-3xl font-bold text-amber-400';
    } else {
        rankEl.textContent = `${ordinal(rankNum)} Place`;
        rankEl.className = 'text-3xl font-bold text-slate-300';
    }

    // Leaderboard
    const lbDiv = document.getElementById('final-leaderboard');
    lbDiv.innerHTML = '';
    const medals = ['🥇', '🥈', '🥉'];
    msg.final_rankings.slice(0, 10).forEach((r, i) => {
        const row = document.createElement('div');
        row.className = `lb-row ${r.player_id === playerId ? 'highlight' : ''}`;
        const medal = i < 3 ? medals[i] : '';
        const youTag = r.player_id === playerId ? ' (You)' : '';
        row.innerHTML = `
            <span>
                <span class="lb-rank font-bold mr-2">${medal || (i + 1) + '.'}</span>
                <span>${r.name}${youTag}</span>
            </span>
            <span class="font-semibold text-indigo-300">${r.total_score.toLocaleString()} pts</span>
        `;
        lbDiv.appendChild(row);
    });

    gameFinished = true;
    showScreen('screen-final');
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function ordinal(n) {
    if (typeof n !== 'number' || n < 1) return n;
    const s = ['th', 'st', 'nd', 'rd'];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
