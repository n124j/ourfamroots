/**
 * Playwright global setup — verifies the backend API is reachable before tests run.
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

function loadEnvVar(name: string): string | undefined {
  if (process.env[name]) return process.env[name];
  try {
    const content = readFileSync(resolve(__dirname, '../../.env'), 'utf-8');
    const match = content.match(new RegExp(`^${name}=(.+)$`, 'm'));
    return match?.[1]?.trim();
  } catch {
    return undefined;
  }
}

const API_URL = loadEnvVar('VITE_API_BASE_URL') ?? 'http://localhost:7004/api/v1';
const HEALTH_URL = API_URL.startsWith('http')
  ? API_URL.replace(/\/api\/v1$/, '') + '/health'
  : 'http://localhost:7004/health';

async function globalSetup() {
  try {
    const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(5_000) });
    if (!res.ok) {
      throw new Error(`Backend health check returned ${res.status}`);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(
      '\n' +
      '╔══════════════════════════════════════════════════════════════════╗\n' +
      '║  Backend API is not reachable!                                 ║\n' +
      '║                                                                ║\n' +
      '║  E2E tests require the backend to be running.                  ║\n' +
      '║  Start it with:  docker compose up -d db redis api migrate     ║\n' +
      '║                                                                ║\n' +
      `║  Health URL: ${HEALTH_URL.padEnd(49)}║\n` +
      `║  Error:      ${msg.slice(0, 49).padEnd(49)}║\n` +
      '╚══════════════════════════════════════════════════════════════════╝\n',
    );
    process.exit(1);
  }
}

export default globalSetup;
