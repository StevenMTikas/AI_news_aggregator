// AI News Aggregator - Frontend JavaScript

let currentTaskId = null;
let pollingInterval = null;

// DOM Elements
const inputCard = document.getElementById('inputCard');
const progressCard = document.getElementById('progressCard');
const resultsCard = document.getElementById('resultsCard');
const errorCard = document.getElementById('errorCard');

const blogForm = document.getElementById('blogForm');
const topicInput = document.getElementById('topic');
const topicSlugInput = document.getElementById('topicSlug');
const generateBtn = document.getElementById('generateBtn');

const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusMessage = document.getElementById('statusMessage');

const downloadBtn = document.getElementById('downloadBtn');
const viewBtn = document.getElementById('viewBtn');
const newPostBtn = document.getElementById('newPostBtn');
const retryBtn = document.getElementById('retryBtn');

const previewContent = document.getElementById('previewContent');
const contentPreview = document.getElementById('contentPreview');
const errorMessage = document.getElementById('errorMessage');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    blogForm.addEventListener('submit', handleFormSubmit);
    viewBtn.addEventListener('click', togglePreview);
    downloadBtn.addEventListener('click', handleDownload);
    newPostBtn.addEventListener('click', resetForm);
    retryBtn.addEventListener('click', resetForm);
}

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const topic = topicInput.value.trim();
    const topicSlug = topicSlugInput.value.trim();
    
    if (!topic || topic.length < 3) {
        showError('Please enter a topic with at least 3 characters.');
        return;
    }
    
    showCard('progress');
    
    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                topic: topic,
                topic_slug: topicSlug || null
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start blog generation');
        }
        
        const data = await response.json();
        currentTaskId = data.task_id;
        
        startPolling();
        
    } catch (error) {
        console.error('Error:', error);
        showError(error.message);
    }
}

function startPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }
    
    pollingInterval = setInterval(checkStatus, 2000);
    checkStatus();
}

async function checkStatus() {
    if (!currentTaskId) return;
    
    try {
        const response = await fetch(`/api/status/${currentTaskId}`);
        
        if (!response.ok) {
            throw new Error('Failed to get task status');
        }
        
        const data = await response.json();
        
        updateProgress(data.progress, data.message);
        
        if (data.status === 'completed') {
            stopPolling();
            await handleCompletion(data);
        } else if (data.status === 'failed') {
            stopPolling();
            showError(data.message);
        }
        
    } catch (error) {
        console.error('Error checking status:', error);
        stopPolling();
        showError('Lost connection to server. Please try again.');
    }
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function updateProgress(progress, message) {
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${progress}%`;
    statusMessage.textContent = message;
}

async function handleCompletion(data) {
    try {
        const response = await fetch(`/api/result/${currentTaskId}`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch result');
        }
        
        const result = await response.json();
        
        downloadBtn.dataset.url = result.download_url;
        contentPreview.textContent = result.content;
        
        showCard('results');
        
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to retrieve the generated content.');
    }
}

function handleDownload() {
    const url = downloadBtn.dataset.url;
    if (url) {
        window.location.href = url;
    }
}

function togglePreview() {
    previewContent.classList.toggle('hidden');
    
    if (previewContent.classList.contains('hidden')) {
        viewBtn.querySelector('.btn-text').textContent = 'View Content';
        viewBtn.querySelector('.btn-icon').textContent = '👁️';
    } else {
        viewBtn.querySelector('.btn-text').textContent = 'Hide Content';
        viewBtn.querySelector('.btn-icon').textContent = '🙈';
    }
}

function showCard(cardName) {
    inputCard.classList.add('hidden');
    progressCard.classList.add('hidden');
    resultsCard.classList.add('hidden');
    errorCard.classList.add('hidden');
    
    switch(cardName) {
        case 'input':
            inputCard.classList.remove('hidden');
            break;
        case 'progress':
            progressCard.classList.remove('hidden');
            break;
        case 'results':
            resultsCard.classList.remove('hidden');
            break;
        case 'error':
            errorCard.classList.remove('hidden');
            break;
    }
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showError(message) {
    errorMessage.textContent = message;
    showCard('error');
}

function resetForm() {
    stopPolling();
    
    blogForm.reset();
    currentTaskId = null;
    
    progressFill.style.width = '0%';
    progressText.textContent = '0%';
    statusMessage.textContent = 'Initializing...';
    
    previewContent.classList.add('hidden');
    
    showCard('input');
}

topicInput.addEventListener('input', (e) => {
    if (!topicSlugInput.value) {
        const slug = generateSlug(e.target.value);
        topicSlugInput.value = slug;
    }
});

function generateSlug(text) {
    return text
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .substring(0, 60);
}

window.addEventListener('offline', () => {
    showError('You appear to be offline. Please check your internet connection.');
});

window.addEventListener('online', () => {
    if (currentTaskId && progressCard.classList.contains('hidden') === false) {
        startPolling();
    }
});

