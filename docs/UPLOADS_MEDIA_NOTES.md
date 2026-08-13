# Uploads — media playback notes

Reference for how the uploads library handles video playback, and the decisions
behind it.

## Which files play in the browser

`website/js/uploads.js` distinguishes two things:

- **`isVideoFile(ext)`** — is this a video at all? `.mp4`, `.avi`, `.mkv`.
- **`isBrowserPlayable(ext)`** — can a browser play it inline? **`.mp4` only**
  (H.264/AAC). `.avi` and `.mkv` are *not* natively playable in browsers.

Only `isBrowserPlayable` gates inline playback (the modal player and the
detail-page `<video>`). For a video that is not browser-playable (`.avi`/`.mkv`)
the UI shows a clear "isn't playable in the browser — download to watch" state
instead of a broken player, and the list card shows a "DL only" chip in place of
the Watch button.

## Future: server-side `.mp4` transcode (owner option 3)

The owner's chosen direction is to keep `.avi`/`.mkv` **download-only for now**
and add a **server-side transcode to `.mp4` on upload** later, so every clip
becomes browser-playable. That needs **`ffmpeg` on the server** (not currently
installed — an infra change). When added:

1. On upload of a non-`.mp4` video, transcode to `.mp4` (H.264/AAC) and store the
   `.mp4` as the playable rendition (keep or drop the original per retention).
2. Mark the row playable so `isBrowserPlayable` / `is_playable` returns true.
3. Drop the "DL only" / "not playable" UI branches for transcoded clips.

Until then, the download path is the reliable way to watch `.avi`/`.mkv`.

## Video lifecycle (why audio used to keep playing)

The video modal is appended to `document.body` and the detail `<video>` lives in
a section the SPA router only hides. Navigating away therefore left media
playing (HTML5 only auto-pauses on DOM *removal*). `website/js/media-cleanup.js`
exposes `closeAllMedia()`, called at the top of `dispatchRoute()` in `app.js`, so
every route change pauses + releases all media at the root.
