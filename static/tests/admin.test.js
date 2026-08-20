import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadAdminModule() {
    const html = fs.readFileSync(path.resolve(__dirname, '../admin.html'), 'utf-8');
    document.documentElement.innerHTML = html;

    vi.resetModules();
    return require('../admin.js');
}

describe('escapeHtml', () => {
    let escapeHtml;

    beforeEach(() => {
        ({ escapeHtml } = loadAdminModule());
    });

    it('escapes HTML special characters', () => {
        expect(escapeHtml('<script>alert(1)</script>')).toBe(
            '&lt;script&gt;alert(1)&lt;/script&gt;'
        );
    });

    it('leaves plain text unchanged', () => {
        expect(escapeHtml('Acme Launch')).toBe('Acme Launch');
    });

    it('escapes ampersands', () => {
        expect(escapeHtml('Tools & Tips')).toBe('Tools &amp; Tips');
    });
});
