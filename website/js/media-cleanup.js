// media-cleanup.js — one place that tears down playing media on route change.
//
// The bug this fixes (confirmed live with headless Chromium): the uploads video
// modal is appended to document.body, decoupled from the SPA router, and the
// inline detail-page <video> lives in a section the router only HIDES (never
// removes). So navigating away — browser back, a nav click, a hash alias — left
// the audio playing in the background, and the detail videos even accumulated.
//
// HTML5 auto-pauses a <video> only when it is REMOVED from the document, which
// never happened here. dispatchRoute() calls closeAllMedia() before switching
// views, so every navigation tears media down at the root, whatever opened it.

/**
 * Stop and release a single <video>: pause, drop its source, and reload so the
 * browser frees the buffered stream (pausing alone can keep the download and
 * memory alive — the pause+clear-src+load idiom is the documented fix).
 */
function _releaseVideo(video) {
    if (!video) return;
    try {
        video.pause();
        // Detach every source: some players set <source> children, some set the
        // src attribute directly.
        video.querySelectorAll('source').forEach((s) => s.removeAttribute('src'));
        video.removeAttribute('src');
        // load() applies the now-empty source set, aborting the network fetch.
        video.load();
    } catch {
        // Best-effort: a detached/partially-torn element must never throw here
        // and abort the route change.
    }
}

/**
 * Tear down all playing media before a route change. Removes the uploads video
 * modal outright and releases every remaining <video> (e.g. the inline
 * detail-page player in a hidden-but-not-removed section). Safe to call on every
 * navigation, including when nothing is playing.
 */
export function closeAllMedia() {
    // Prefer the uploads modal's OWN teardown when present: it removes the
    // document keydown listener, releases the video, and restores focus — doing
    // it here by hand would leave that listener attached and leak one per
    // open-then-navigate-away cycle (CodeRabbit/Copilot #717). It's a window
    // global set by uploads.js, so this is a no-op if uploads never loaded.
    if (typeof window !== 'undefined' && typeof window.closeVideoPlayer === 'function') {
        window.closeVideoPlayer();
    } else {
        const modal = document.getElementById('video-player-modal');
        if (modal) {
            _releaseVideo(modal.querySelector('video'));
            modal.remove();
        }
    }
    // Release any other <video> (e.g. the inline detail-page player in a section
    // the router only hides). Idempotent with the modal teardown above.
    document.querySelectorAll('video').forEach(_releaseVideo);
}
