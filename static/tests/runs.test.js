import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function load(file, html) {
    document.documentElement.innerHTML = fs.readFileSync(path.resolve(__dirname, `../${html}`), 'utf-8');
    vi.resetModules();
    return require(`../${file}`);
}

describe('runs.js', () => {
    let mod;
    beforeEach(() => {
        mod = load('runs.js', 'runs.html');
    });

    it('escapes html in a run row', () => {
        const row = mod.rowFor({
            id: 'abc123', topic: '<b>x</b>', kind: 'atomic', status: 'completed',
            cost_usd: 0.123, created_at: '2026-09-07T12:00:00',
        });
        expect(row).toContain('&lt;b&gt;x&lt;/b&gt;');
        expect(row).toContain('$0.1230');
        expect(row).toContain('status-completed');
        expect(row).toContain('data-run="abc123"');
    });

    it('escapeHtml handles null', () => {
        expect(mod.escapeHtml(null)).toBe('');
    });
});

describe('compile.js', () => {
    it('loads against compile.html without throwing', () => {
        const mod = load('compile.js', 'compile.html');
        expect(mod.escapeHtml('<i>')).toBe('&lt;i&gt;');
    });
});
