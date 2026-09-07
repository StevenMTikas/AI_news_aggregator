// ContentForge - Admin Dashboard

let editingSlug = null;

const listCard = document.getElementById('listCard');
const formCard = document.getElementById('formCard');
const errorCard = document.getElementById('errorCard');
const projectListContainer = document.getElementById('projectListContainer');
const errorMessage = document.getElementById('errorMessage');

const projectForm = document.getElementById('projectForm');
const formTitle = document.getElementById('formTitle');
const slugInput = document.getElementById('slug');
const nameInput = document.getElementById('name');
const audienceInput = document.getElementById('audience');
const toneInput = document.getElementById('tone');
const categoryTagsInput = document.getElementById('categoryTags');
const authorInput = document.getElementById('author');
const targetWordCountInput = document.getElementById('targetWordCount');
const notesInput = document.getElementById('notes');
const subjectFocusInput = document.getElementById('subjectFocus');
const styleGuideInput = document.getElementById('styleGuide');
const bannedPhrasesInput = document.getElementById('bannedPhrases');
const recencyDaysInput = document.getElementById('recencyDays');
const minSourcesInput = document.getElementById('minSources');
const preferDomainsInput = document.getElementById('preferDomains');
const excludeDomainsInput = document.getElementById('excludeDomains');
const defaultModelInput = document.getElementById('defaultModel');

const csv = (value) => value.split(',').map((t) => t.trim()).filter(Boolean);

const newProjectBtn = document.getElementById('newProjectBtn');
const cancelFormBtn = document.getElementById('cancelFormBtn');
const dismissErrorBtn = document.getElementById('dismissErrorBtn');

document.addEventListener('DOMContentLoaded', () => {
    newProjectBtn.addEventListener('click', () => showForm(null));
    cancelFormBtn.addEventListener('click', showList);
    dismissErrorBtn.addEventListener('click', showList);
    projectForm.addEventListener('submit', handleSubmit);
    loadProjects();
});

async function loadProjects() {
    try {
        const response = await fetch('/api/projects');
        if (!response.ok) throw new Error('Failed to load projects');
        const projects = await response.json();
        renderProjectList(projects);
    } catch (error) {
        showError(error.message);
    }
}

function renderProjectList(projects) {
    if (!projects.length) {
        projectListContainer.innerHTML = '<p class="empty-state">No projects yet. Create one to get started.</p>';
        return;
    }

    const rows = projects.map(p => `
        <tr>
            <td>${escapeHtml(p.name)}</td>
            <td>${escapeHtml(p.audience)}</td>
            <td>${escapeHtml(p.tone)}</td>
            <td class="row-actions">
                <button class="btn btn-secondary btn-small" data-action="edit" data-slug="${escapeHtml(p.slug)}">Edit</button>
                <button class="btn btn-danger btn-small" data-action="delete" data-slug="${escapeHtml(p.slug)}">Delete</button>
            </td>
        </tr>
    `).join('');

    projectListContainer.innerHTML = `
        <table class="project-table">
            <thead>
                <tr><th>Name</th><th>Audience</th><th>Tone</th><th>Actions</th></tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;

    projectListContainer.querySelectorAll('[data-action="edit"]').forEach(btn => {
        btn.addEventListener('click', () => editProject(btn.dataset.slug));
    });
    projectListContainer.querySelectorAll('[data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', () => deleteProject(btn.dataset.slug));
    });
}

async function editProject(slug) {
    try {
        const response = await fetch(`/api/projects/${encodeURIComponent(slug)}`);
        if (!response.ok) throw new Error('Failed to load project');
        const project = await response.json();
        showForm(project);
    } catch (error) {
        showError(error.message);
    }
}

async function deleteProject(slug) {
    if (!confirm(`Delete project "${slug}"? Already-generated content is not affected.`)) return;
    try {
        const response = await fetch(`/api/projects/${encodeURIComponent(slug)}`, { method: 'DELETE' });
        if (!response.ok && response.status !== 204) throw new Error('Failed to delete project');
        loadProjects();
    } catch (error) {
        showError(error.message);
    }
}

function showForm(project) {
    editingSlug = project ? project.slug : null;
    formTitle.textContent = project ? `Edit ${project.name}` : 'New Project';
    slugInput.value = project ? project.slug : '';
    slugInput.disabled = !!project;
    nameInput.value = project ? project.name : '';
    audienceInput.value = project ? project.audience : '';
    toneInput.value = project ? project.tone : '';
    categoryTagsInput.value = project ? project.category_tags.join(', ') : '';
    authorInput.value = project ? project.author : '';
    targetWordCountInput.value = project ? project.target_word_count : 800;
    notesInput.value = project && project.notes ? project.notes : '';
    subjectFocusInput.value = project ? project.subject_focus || '' : '';
    styleGuideInput.value = project ? project.style_guide || '' : '';
    bannedPhrasesInput.value = project ? (project.banned_phrases || []).join(', ') : '';
    recencyDaysInput.value = project && project.recency_days ? project.recency_days : '';
    minSourcesInput.value = project ? project.min_sources ?? 5 : 5;
    preferDomainsInput.value = project ? (project.prefer_domains || []).join(', ') : '';
    excludeDomainsInput.value = project ? (project.exclude_domains || []).join(', ') : '';
    defaultModelInput.value = project ? project.default_model || '' : '';

    listCard.classList.add('hidden');
    errorCard.classList.add('hidden');
    formCard.classList.remove('hidden');
}

function showList() {
    formCard.classList.add('hidden');
    errorCard.classList.add('hidden');
    listCard.classList.remove('hidden');
    slugInput.disabled = false;
    loadProjects();
}

async function handleSubmit(e) {
    e.preventDefault();

    const body = {
        name: nameInput.value.trim(),
        audience: audienceInput.value.trim(),
        tone: toneInput.value.trim(),
        category_tags: csv(categoryTagsInput.value),
        author: authorInput.value.trim(),
        target_word_count: parseInt(targetWordCountInput.value, 10) || 800,
        notes: notesInput.value.trim() || null,
        subject_focus: subjectFocusInput.value.trim(),
        style_guide: styleGuideInput.value.trim(),
        banned_phrases: csv(bannedPhrasesInput.value),
        recency_days: parseInt(recencyDaysInput.value, 10) || null,
        min_sources: parseInt(minSourcesInput.value, 10) || 5,
        prefer_domains: csv(preferDomainsInput.value),
        exclude_domains: csv(excludeDomainsInput.value),
        default_model: defaultModelInput.value.trim() || null,
    };

    try {
        let response;
        if (editingSlug) {
            response = await fetch(`/api/projects/${encodeURIComponent(editingSlug)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        } else {
            body.slug = slugInput.value.trim();
            response = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save project');
        }

        showList();
    } catch (error) {
        showError(error.message);
    }
}

function showError(message) {
    errorMessage.textContent = message;
    listCard.classList.add('hidden');
    formCard.classList.add('hidden');
    errorCard.classList.remove('hidden');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Node/Vitest test access only -- no-op in the browser, where `module` is undefined.
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHtml };
}
