const test = require('node:test');
const assert = require('node:assert/strict');
const { refreshStatus } = require('../js/scholar-status.js');
const checked = '2026-11-02T07:23:00Z';
const now = Date.parse(checked);
const day = 24 * 60 * 60 * 1000;

test('baseline is explicitly historical, never checked today', () => {
  const result = refreshStatus('', now);
  assert.equal(result.state, 'historical');
  assert.match(result.message, /not yet verified/);
  assert.doesNotMatch(result.message, /Last successful/);
});
test('last successful check remains dated in UTC', () => {
  assert.equal(refreshStatus(checked, now).state, 'checked');
  assert.match(refreshStatus(checked, now).message, /2 November 2026 \(UTC\)/);
});
test('weekly grace period expires only after 14 days, never rewrites date', () => {
  assert.equal(refreshStatus(checked, now + 14 * day).state, 'checked');
  const overdue = refreshStatus(checked, now + 14 * day + 1);
  assert.equal(overdue.state, 'overdue');
  assert.match(overdue.message, /Update overdue/);
  assert.match(overdue.message, /2 November 2026/);
});
test('invalid or implausibly future dates cannot claim freshness', () => {
  for (const date of ['not-a-date', '2027-01-01T00:00:00Z']) {
    assert.equal(refreshStatus(date, now).state, 'unknown');
  }
});
