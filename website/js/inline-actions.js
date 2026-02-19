const ACTION_ATTR = 'data-click-action';
const PROFILE_NAME_EXPR = "document.getElementById('profile-name').textContent";

function splitArgs(argsRaw) {
    const args = [];
    let current = '';
    let quote = '';
    let escape = false;
    let depth = 0;

    for (const char of argsRaw) {
        if (escape) {
            current += char;
            escape = false;
            continue;
        }
        if (quote) {
            current += char;
            if (char === '\\') {
                escape = true;
            } else if (char === quote) {
                quote = '';
            }
            continue;
        }
        if (char === '\'' || char === '"') {
            quote = char;
            current += char;
            continue;
        }
        if (char === '{' || char === '[' || char === '(') {
            depth += 1;
            current += char;
            continue;
        }
        if (char === '}' || char === ']' || char === ')') {
            depth = Math.max(0, depth - 1);
            current += char;
            continue;
        }
        if (char === ',' && depth === 0) {
            const token = current.trim();
            if (token) args.push(token);
            current = '';
            continue;
        }
        current += char;
    }

    const tail = current.trim();
    if (tail) args.push(tail);
    return args;
}

function parseArgToken(token) {
    if (/^'.*'$/.test(token) || /^".*"$/.test(token)) {
        return token.slice(1, -1);
    }
    if (token === 'true') return true;
    if (token === 'false') return false;
    if (/^-?\d+$/.test(token)) return Number(token);

    const sectionMatch = token.match(/^\{\s*section\s*:\s*'([^']+)'\s*}$/);
    if (sectionMatch) {
        return { section: sectionMatch[1] };
    }

    if (token === PROFILE_NAME_EXPR) {
        return document.getElementById('profile-name')?.textContent || '';
    }

    throw new Error(`Unsupported action arg token: ${token}`);
}

function resolveAction(action) {
    const open = action.indexOf('(');
    const close = action.endsWith(')') ? action.length - 1 : -1;
    if (open <= 0 || close <= open) {
        throw new Error(`Malformed action: ${action}`);
    }

    let fnPath = action.slice(0, open).trim();
    const argsRaw = action.slice(open + 1, close).trim();

    if (fnPath.startsWith('window.')) {
        fnPath = fnPath.slice('window.'.length);
    }

    const parts = fnPath.split('.').filter(Boolean);
    let fnRef = window;
    for (const part of parts) {
        fnRef = fnRef?.[part];
    }

    if (typeof fnRef !== 'function') {
        throw new Error(`Action target is not a function: ${fnPath}`);
    }

    const args = argsRaw ? splitArgs(argsRaw).map(parseArgToken) : [];
    return { fnRef, args };
}

function invokeAction(action, event) {
    const { fnRef, args } = resolveAction(action);
    return fnRef.apply(window, args);
}

export function bindInlineClickActions(root = document) {
    root.querySelectorAll(`[${ACTION_ATTR}]`).forEach((element) => {
        if (element.dataset.clickActionBound === 'true') return;
        const action = (element.getAttribute(ACTION_ATTR) || '').trim();
        if (!action) return;

        element.addEventListener('click', (event) => {
            if (element.tagName === 'A') {
                const href = element.getAttribute('href') || '';
                if (href.startsWith('#')) {
                    event.preventDefault();
                }
            }
            try {
                invokeAction(action, event);
            } catch (err) {
                console.warn(`Failed to invoke click action: ${action}`, err);
            }
        });

        element.dataset.clickActionBound = 'true';
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => bindInlineClickActions());
} else {
    bindInlineClickActions();
}

window.bindInlineClickActions = bindInlineClickActions;
