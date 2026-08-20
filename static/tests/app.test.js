import { describe, it, expect, beforeEach, vi } from 'vitest';
import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadAppModule() {
    const html = fs.readFileSync(path.resolve(__dirname, '../index.html'), 'utf-8');
    document.documentElement.innerHTML = html;

    vi.resetModules();
    return require('../app.js');
}

describe('generateSlug', () => {
    let generateSlug;

    beforeEach(() => {
        ({ generateSlug } = loadAppModule());
    });

    it('lowercases and hyphenates', () => {
        expect(generateSlug('Best AI Tools for Restaurants')).toBe('best-ai-tools-for-restaurants');
    });

    it('strips special characters', () => {
        expect(generateSlug('AI & ML: What\'s Next?!')).toBe('ai-ml-whats-next');
    });

    it('collapses repeated separators', () => {
        expect(generateSlug('  extra   spaces_and-hyphens  ')).toBe('extra-spaces-and-hyphens');
    });

    it('truncates to 60 characters', () => {
        const long = 'a'.repeat(100);
        expect(generateSlug(long).length).toBe(60);
    });
});

describe('renderContentPreview', () => {
    let renderContentPreview;

    beforeEach(() => {
        ({ renderContentPreview } = loadAppModule());
    });

    it('returns an empty string for null content', () => {
        expect(renderContentPreview(null)).toBe('');
    });

    it('renders title, hook, sections, key points, and CTA', () => {
        const content = {
            title: 'My Post',
            hook: 'A hook.',
            sections: [
                { heading: 'Section One', body: 'Body one.', pull_quote: 'A quote.' },
                { heading: 'Section Two', body: 'Body two.', pull_quote: null },
            ],
            key_points: ['Point A', 'Point B'],
            call_to_action: 'Do the thing.',
        };

        const preview = renderContentPreview(content);

        expect(preview).toContain('# My Post');
        expect(preview).toContain('A hook.');
        expect(preview).toContain('## Section One');
        expect(preview).toContain('> A quote.');
        expect(preview).toContain('## Section Two');
        expect(preview).not.toContain('Section Two\n\nBody two.\n\n>');
        expect(preview).toContain('## Key Takeaways');
        expect(preview).toContain('- Point A');
        expect(preview).toContain('- Point B');
        expect(preview).toContain('Do the thing.');
    });

    it('omits the Key Takeaways heading when there are no key points', () => {
        const content = {
            title: 'My Post',
            hook: 'A hook.',
            sections: [],
            key_points: [],
            call_to_action: null,
        };

        expect(renderContentPreview(content)).not.toContain('Key Takeaways');
    });
});
