// ContentForge - Run history

const projectSelect = document.getElementById('project');
const runsContainer = document.getElementById('runsContainer');
const costSummary = document.getElementById('costSummary');
const detailCard = document.getElementById('detailCard');
const detailTitle = document.getElementById('detailTitle');
const detailMeta = document.getElementById('detailMeta');
const detailDocs = document.getElementById('detailDocs');

document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
    projectSelect.addEventListener('change', refresh);
    document.getElementById('backBtn').addEventListener('click', () => {
        detailCard.classList.add('hidden');
    });
    refresh();
});

async function loadProjects() {
    const projects = await fetch('/api/projects').then((r) => r.json());
    projectSelect.innerHTML = '<option value="">All projects</option>' +
        projects.map((p) => `<option value="${p.slug}">${escapeHtml(p.name)}</option>`).join('');
}

async function refresh() {
    const slug = projectSelect.value;
    const runs = await fetch(`/api/runs?limit=50${slug ? `&project_slug=${encodeURIComponent(slug)}` : ''}`).then((r) => r.json());

    if (slug) {
        const c = await fetch(`/api/costs?project_slug=${encodeURIComponent(slug)}`).then((r) => r.json());
        costSummary.textContent = `${c.runs} run(s) · $${(c.usd || 0).toFixed(4)} · ${c.search_calls || 0} searches`;
    } else {
        costSummary.textContent = '';
    }

    if (!runs.length) {
        runsContainer.innerHTML = '<p class="empty-state">No runs yet.</p>';
        return;
    }
    runsContainer.innerHTML = `
        <table class="project-table">
            <thead><tr><th>Topic</th><th>Kind</th><th>Status</th><th>Cost</th><th>When</th><th></th></tr></thead>
            <tbody>${runs.map(rowFor).join('')}</tbody>
        </table>`;
    runsContainer.querySelectorAll('[data-run]').forEach((btn) => {
        btn.addEventListener('click', () => showDetail(btn.dataset.run));
    });
}

function rowFor(r) {
    return `<tr>
        <td>${escapeHtml(r.topic)}</td>
        <td>${r.kind}</td>
        <td><span class="status-${r.status}">${r.status}</span></td>
        <td>$${(r.cost_usd || 0).toFixed(4)}</td>
        <td>${r.created_at.slice(0, 16).replace('T', ' ')}</td>
        <td><button class="btn btn-secondary btn-small" data-run="${r.id}">Open</button></td>
    </tr>`;
}

async function showDetail(runId) {
    const detail = await fetch(`/api/runs/${runId}`).then((r) => r.json());
    const run = detail.run;
    detailTitle.textContent = `${run.kind} — ${run.topic}`;
    detailMeta.innerHTML =
        `<span class="status-${run.status}">${run.status}</span> · ` +
        `$${(run.cost_usd || 0).toFixed(4)} · ${run.tokens_in + run.tokens_out} tokens · ` +
        `${run.search_calls} searches · ${run.created_at.slice(0, 16).replace('T', ' ')}` +
        (run.message ? `<br><em>${escapeHtml(run.message)}</em>` : '');

    const bd = detail.cost_breakdown || [];
    const breakdown = bd.length
        ? `<table class="project-table"><thead><tr><th>kind</th><th>model</th><th>tokens</th><th>$</th></tr></thead><tbody>` +
          bd.map((b) => `<tr><td>${b.kind}</td><td>${escapeHtml(b.model || '-')}</td><td>${(b.tokens_in || 0) + (b.tokens_out || 0)}</td><td>$${(b.usd || 0).toFixed(4)}</td></tr>`).join('') +
          `</tbody></table>`
        : '';

    const docs = detail.documents || [];
    detailDocs.innerHTML = breakdown + (docs.length
        ? docs.map(docRow).join('')
        : '<p class="empty-state">No documents.</p>');
    detailDocs.querySelectorAll('[data-render]').forEach((btn) => {
        btn.addEventListener('click', () => rerender(btn.dataset.render, btn));
    });
    detailCard.classList.remove('hidden');
    detailCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function docRow(d) {
    const dl = d.download_url ? `<a class="btn btn-secondary btn-small" href="${d.download_url}">Download</a>` : '';
    const review = d.type === 'metadata' ? '' :
        `<span class="review-${d.review_status}">${d.review_status}</span>` +
        (d.review_notes ? ` <small>${escapeHtml(d.review_notes)}</small>` : '');
    const prov = (d.based_on_brief_ids || []).length
        ? `<small class="prov">from ${d.based_on_brief_ids.length} brief(s)` +
          ((d.based_on_document_ids || []).length ? `, ${d.based_on_document_ids.length} doc(s)` : '') + '</small>'
        : '';
    return `<div class="doc-row">
        <strong>${escapeHtml(d.type)}</strong> — ${escapeHtml(d.title || '(untitled)')} ${review} ${prov}
        <span class="doc-actions">${dl}
            <button class="btn btn-secondary btn-small" data-render="${d.id}">Re-render</button>
        </span>
    </div>`;
}

async function rerender(docId, btn) {
    btn.disabled = true;
    btn.textContent = '…';
    try {
        const res = await fetch(`/api/documents/${docId}/render`, { method: 'POST' });
        const data = await res.json();
        btn.textContent = res.ok ? 'Re-rendered' : 'Failed';
        if (res.ok && data.download_url) window.open(data.download_url);
    } catch (_) {
        btn.textContent = 'Failed';
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : str;
    return div.innerHTML;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHtml, rowFor };
}
