// ContentForge - Compile long-form

const projectSelect = document.getElementById('project');
const longformType = document.getElementById('longformType');
const angleInput = document.getElementById('angle');
const runList = document.getElementById('runList');
const lastNRuns = document.getElementById('lastNRuns');
const lastNDays = document.getElementById('lastNDays');
const selectionCount = document.getElementById('selectionCount');
const compileForm = document.getElementById('compileForm');

const formCard = document.getElementById('formCard');
const progressCard = document.getElementById('progressCard');
const resultsCard = document.getElementById('resultsCard');
const errorCard = document.getElementById('errorCard');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusMessage = document.getElementById('statusMessage');
const resultTitle = document.getElementById('resultTitle');
const errorMessage = document.getElementById('errorMessage');

let pollTimer = null;
let downloadUrl = null;

document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    projectSelect.addEventListener('change', loadRuns);
    runList.addEventListener('change', updateCount);
    compileForm.addEventListener('submit', submit);
    document.getElementById('downloadBtn').addEventListener('click', () => downloadUrl && window.open(downloadUrl));
    document.getElementById('againBtn').addEventListener('click', reset);
    document.getElementById('retryBtn').addEventListener('click', reset);
});

async function loadProjects() {
    const projects = await fetch('/api/projects').then((r) => r.json());
    projectSelect.innerHTML = '<option value="">Select a project&hellip;</option>' +
        projects.map((p) => `<option value="${p.slug}">${escapeHtml(p.name)}</option>`).join('');
}

async function loadRuns() {
    const slug = projectSelect.value;
    if (!slug) { runList.innerHTML = '<p class="empty-state">Select a project to load its runs.</p>'; return; }
    const runs = await fetch(`/api/runs?project_slug=${encodeURIComponent(slug)}&kind=atomic&limit=40`).then((r) => r.json());
    if (!runs.length) { runList.innerHTML = '<p class="empty-state">No atomic runs yet for this project.</p>'; return; }
    runList.innerHTML = runs.map((r) => `
        <label class="run-row">
            <input type="checkbox" value="${r.id}">
            <span>${escapeHtml(r.topic)}</span>
            <small>${r.created_at.slice(0, 10)} &middot; ${r.status}</small>
        </label>`).join('');
    updateCount();
}

function selectedRunIds() {
    return [...runList.querySelectorAll('input:checked')].map((el) => el.value);
}

function updateCount() {
    const n = selectedRunIds().length;
    selectionCount.textContent = n ? `${n} run${n === 1 ? '' : 's'} selected` : '';
}

async function submit(e) {
    e.preventDefault();
    const body = {
        project_slug: projectSelect.value,
        longform_type: longformType.value,
        angle: angleInput.value.trim(),
        run_ids: selectedRunIds(),
        last_n_runs: parseInt(lastNRuns.value, 10) || null,
        last_n_days: parseInt(lastNDays.value, 10) || null,
    };
    show(progressCard);
    try {
        const res = await fetch('/api/compile', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error((await res.json()).detail || 'Failed to start');
        poll((await res.json()).task_id);
    } catch (err) {
        fail(err.message);
    }
}

function poll(taskId) {
    pollTimer = setInterval(async () => {
        const s = await fetch(`/api/status/${taskId}`).then((r) => r.json());
        progressFill.style.width = `${s.progress}%`;
        progressText.textContent = `${s.progress}%`;
        statusMessage.textContent = s.message;
        if (s.status === 'completed') {
            clearInterval(pollTimer);
            downloadUrl = s.download_url;
            resultTitle.textContent = (s.result && (s.result.subject || s.result.title)) || 'Ready';
            show(resultsCard);
        } else if (s.status === 'failed') {
            clearInterval(pollTimer);
            fail(s.message);
        }
    }, 1500);
}

function show(card) {
    [formCard, progressCard, resultsCard, errorCard].forEach((c) => c.classList.add('hidden'));
    card.classList.remove('hidden');
}

function fail(msg) {
    if (pollTimer) clearInterval(pollTimer);
    errorMessage.textContent = msg;
    show(errorCard);
}

function reset() {
    show(formCard);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHtml };
}
