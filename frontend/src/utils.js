// Try to close this tab (works when it was opened from the app).
// Falls back to an in-tab navigation when the browser refuses.
export function closeTabOr(fallback) {
  window.close();
  setTimeout(() => {
    if (!window.closed) fallback();
  }, 150);
}
