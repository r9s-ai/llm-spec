
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';

import { loadDotEnvIfPresent } from '../api-sdk-tester/environment/runtime-config';
import type { BillingRecord } from './type';

export const DEFAULT_BILLING_ARTIFACT_PATH = 'src/billing-audit/data/billing.json';
interface FetchBillingOptions {
  url?: string;
  bearerToken?: string;
  /** Unix timestamp in seconds. */
  startTime: string;
  /** Unix timestamp in seconds. */
  endTime: string;
  outputPath?: string;
}

function firstNonEmptyEnv(...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = process.env[key];
    if (value?.trim()) {
      return value.trim();
    }
  }
  return undefined;
}

function assertUnixTimeSeconds(name: string, value: string): void {
  if (!/^\d+$/.test(value)) {
    throw new Error(`${name} must be a Unix timestamp in seconds`);
  }
}

export async function fetchBilling({
  url,
  bearerToken,
  startTime,
  endTime,
  outputPath,
}: FetchBillingOptions): Promise<BillingRecord> {
  loadDotEnvIfPresent();
  const resolvedUrl = url ?? firstNonEmptyEnv('BILLING_BASE_URL');
  const resolvedBearerToken =
    bearerToken ?? firstNonEmptyEnv('BILLING_API_KEY');

  if (!resolvedUrl) {
    throw new Error('missing billing url (pass url or set BILLING_BASE_URL)');
  }
  if (!resolvedBearerToken) {
    throw new Error('missing billing bearer token (pass bearerToken or set BILLING_API_KEY)');
  }
  assertUnixTimeSeconds('startTime', startTime);
  assertUnixTimeSeconds('endTime', endTime);

  const parsedUrl = new URL(resolvedUrl);
  parsedUrl.searchParams.set('start_time', startTime);
  parsedUrl.searchParams.set('end_time', endTime);

  const resp = await fetch(parsedUrl, {
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${resolvedBearerToken}`,
    },
  });
  if (!resp.ok) {
    throw new Error(`fetch billing failed: ${resp.status} ${resp.statusText}`);
  }

  const billing = (await resp.json()) as BillingRecord;
  writeBillingArtifact(billing, outputPath);
  return billing;
}

async function runCli(): Promise<void> {
  loadDotEnvIfPresent();
  const args = process.argv.slice(2);
  const startTime = args[0] ?? process.env['BILLING_START_TIME'];
  const endTime = args[1] ?? process.env['BILLING_END_TIME'];

  if (!startTime || !endTime) {
    console.error(
      'Usage: tsx src/billing-audit/fetch-billing.ts <startTime> <endTime>',
    );
    console.error(
      '  startTime / endTime must be Unix timestamps in seconds.',
    );
    console.error(
      '  Also accepts BILLING_START_TIME / BILLING_END_TIME env vars.',
    );
    process.exit(2);
  }

  try {
    const billing = await fetchBilling({ startTime, endTime });
    console.log('billing fetched, total records:', billing.data?.total);
    const artifactPath =
      resolvePath(process.cwd(), DEFAULT_BILLING_ARTIFACT_PATH);
    console.log('artifact written:', artifactPath);
  } catch (error: unknown) {
    console.error(
      'fetch billing failed:',
      error instanceof Error ? error.message : error,
    );
    process.exit(1);
  }
}

const isDirectInvocation =
  process.argv[1]?.includes('fetch-billing') === true;

if (isDirectInvocation) {
  runCli();
}

export function writeBillingArtifact(
  billing: BillingRecord,
  path = DEFAULT_BILLING_ARTIFACT_PATH,
): string {
  const artifactPath = resolvePath(process.cwd(), path);
  mkdirSync(dirname(artifactPath), { recursive: true });
  writeFileSync(artifactPath, `${JSON.stringify(billing, null, 2)}\n`, 'utf8');
  return artifactPath;
}
