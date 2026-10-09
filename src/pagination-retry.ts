export function isAccessBlock(message: string): boolean {
  return /\b403\b|\b429\b|captcha|cloudflare|verify you are human|access denied/i.test(message);
}

export function canDeferZip(message: string): boolean {
  return !isAccessBlock(message) && /timed out|timeout|ETIMEDOUT/i.test(message);
}

// Check again before retrying: a late response must not cause a second advance.
export async function advanceWithRetry(options: {
  changed: () => Promise<boolean>;
  trigger: (attempt: number) => Promise<void>;
  pending: () => boolean;
  wait: (milliseconds: number) => Promise<boolean>;
  note: (message: string) => void;
}): Promise<void> {
  for (let attempt = 0; attempt < 2; attempt++) {
    if (await options.changed()) return;
    if (!options.pending()) await options.trigger(attempt);
    else options.note('Pagination request is still pending; waiting without clicking again.');
    if (await options.wait(attempt === 0 ? 35_000 : 70_000)) return;
    options.note(`Pagination wait ${attempt + 1} expired; checking for a late response.`);
  }
  if (await options.changed()) return;
  throw new Error('Timed out waiting for the next page of agents after local retry');
}
