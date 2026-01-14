/**
 * Utility functions for Slomix ET:Legacy Stats
 * @module utils
 */

// API endpoints
export const API_BASE = window.location.origin + '/api';
export const AUTH_BASE = window.location.origin + '/auth';

/**
 * Escape HTML special characters to prevent XSS attacks.
 * Use this for any user-controlled data inserted into HTML.
 * @param {string} str - The string to escape
 * @returns {string} - HTML-safe string
 */
export function escapeHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

/**
 * Escape a string for safe use in JavaScript inline handlers (onclick, etc.).
 * This prevents breaking out of quoted attribute values.
 * Use this when inserting user data into onclick="func('${value}')" patterns.
 * @param {string} str - The string to escape
 * @returns {string} - JavaScript-safe string for use in quoted attributes
 */
export function escapeJsString(str) {
    if (str == null) return '';
    return String(str)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n')
        .replace(/\r/g, '\\r')
        .replace(/</g, '\\x3c')
        .replace(/>/g, '\\x3e');
}

/**
 * Safely insert HTML that contains escaped user content.
 * Only use this when ALL user-controlled content has been escaped with escapeHtml().
 * @param {Element} element - The target element
 * @param {string} position - Position to insert ('beforeend', 'afterbegin', etc.)
 * @param {string} html - HTML string with escaped user content
 */
export function safeInsertHTML(element, position, html) {
    element.insertAdjacentHTML(position, html);
}

/**
 * Fetch JSON from an API endpoint
 * @param {string} url - The URL to fetch
 * @returns {Promise<any>} - Parsed JSON response
 */
export async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
}

/**
 * Fetch with retry logic
 * @param {string} url - The URL to fetch
 * @param {object} options - Fetch options
 * @param {number} maxRetries - Maximum retry attempts
 * @returns {Promise<Response>}
 */
export async function fetchWithRetry(url, options = {}, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const res = await fetch(url, options);
            if (res.ok) return res;
        } catch (e) {
            if (i === maxRetries - 1) throw e;
        }
        await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
}

/**
 * Format large numbers nicely (1234 -> 1.2k)
 * @param {number} num - The number to format
 * @returns {string} - Formatted string
 */
export function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
}

/**
 * Format time difference as "X ago"
 * @param {Date} date - The date to compare
 * @returns {string} - Formatted time ago string
 */
export function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

/**
 * Format stopwatch time from seconds
 * @param {number} seconds - Total seconds
 * @returns {string} - Formatted MM:SS string
 */
export function formatStopwatchTime(seconds) {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Show error message to user
 * @param {string} message - Error message to display
 */
export function showError(message) {
    console.error(message);
    // Could add toast notification here
    alert(message);
}

/**
 * Get YouTube video ID from URL
 * @param {string} url - YouTube URL
 * @returns {string|null} - Video ID or null
 */
export function getYouTubeID(url) {
    const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&]+)/);
    return match ? match[1] : null;
}
