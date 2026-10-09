import test from 'node:test';
import assert from 'node:assert/strict';
import { advanceWithRetry, canDeferZip } from './pagination-retry.js';

test('retries a failed transition without restarting the ZIP', async () => {
  const triggers: number[] = [];
  let waits = 0;
  await advanceWithRetry({changed: async () => false, pending: () => false,
    trigger: async attempt => { triggers.push(attempt); },
    wait: async () => ++waits === 2, note: () => {}});
  assert.deepEqual(triggers, [0, 1]);
});
test('late response prevents another click', async () => {
  let checks = 0;
  let clicks = 0;
  await advanceWithRetry({changed: async () => ++checks === 2, pending: () => false,
    trigger: async () => { clicks++; }, wait: async () => false, note: () => {}});
  assert.equal(clicks, 1);
});
test('pending request is given extra time without duplicate clicks', async () => {
  let clicks = 0;
  let waits = 0;
  await advanceWithRetry({changed: async () => false, pending: () => waits > 0,
    trigger: async () => { clicks++; }, wait: async () => ++waits === 2, note: () => {}});
  assert.equal(clicks, 1);
});
test('exhausted transition stays an error', async () => {
  await assert.rejects(advanceWithRetry({changed: async () => false, pending: () => false,
    trigger: async () => {}, wait: async () => false, note: () => {}}), /Timed out/);
});
test('access blocks never become deferred timeouts', async () => {
  assert.equal(canDeferZip('Timed out waiting for the next page'), true);
  for (const message of ['HTTP 429 timeout', '403 timed out', 'captcha timeout', 'access denied', 'broken selector']) {
    assert.equal(canDeferZip(message), false);
  }
  await assert.rejects(advanceWithRetry({changed: async () => { throw new Error('HTTP 429'); },
    pending: () => false, trigger: async () => {}, wait: async () => false, note: () => {}}), /429/);
});
