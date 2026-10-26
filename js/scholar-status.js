/* No API calls or keys in the browser; figures are generated as static HTML. */
(function (root) {
  'use strict';
  const OVERDUE_MS = 14 * 24 * 60 * 60 * 1000;

  function refreshStatus(checkedAt, now = Date.now()) {
    if (!checkedAt) return { state: 'historical', message: 'Historical figures; weekly refresh not yet verified.' };
    const checked = Date.parse(checkedAt);
    if (!Number.isFinite(checked) || checked > now + 5 * 60 * 1000) {
      return { state: 'unknown', message: 'Check date unavailable; see Google Scholar for current figures.' };
    }
    const date = new Intl.DateTimeFormat('en-GB', {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
    }).format(new Date(checked));
    const overdue = now - checked > OVERDUE_MS;
    return {
      state: overdue ? 'overdue' : 'checked',
      message: `Last successful check: ${date} (UTC). ${overdue ? 'Update overdue — showing the last verified figures.' : 'Weekly schedule; figures may change.'}`
    };
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { refreshStatus };
  if (root.document) {
    const update = () => root.document.querySelectorAll('[data-scholar-checked-at]').forEach(element => {
      const status = refreshStatus(element.dataset.scholarCheckedAt);
      element.textContent = status.message;
      element.dataset.refreshState = status.state;
    });
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', update);
    else update();
    // Re-evaluate when a long-open tab is revisited.
    root.document.addEventListener('visibilitychange', () => { if (!root.document.hidden) update(); });
  }
})(typeof window === 'undefined' ? globalThis : window);
