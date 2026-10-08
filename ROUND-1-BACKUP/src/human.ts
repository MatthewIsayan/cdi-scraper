export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function randomBetween(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

export async function humanPause(range: [number, number]): Promise<void> {
  await sleep(randomBetween(range[0], range[1]));
}

export function log(message: string): void {
  const time = new Date().toLocaleTimeString("en-US", { hour12: false });
  console.log(`[${time}] ${message}`);
}
