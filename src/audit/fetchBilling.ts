
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve as resolvePath } from 'node:path';


import {loadDotEnvIfPresent} from "../api-sdk-tester/environment/runtime-config"
import type { BillingRecord } from './type';

export const DEFAULT_BILLING_ARTIFACT_PATH = 'src/audit/billing.json';

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

export function writeBillingArtifact(
  billing: BillingRecord,
  path = DEFAULT_BILLING_ARTIFACT_PATH,
): string {
  const artifactPath = resolvePath(process.cwd(), path);
  mkdirSync(dirname(artifactPath), { recursive: true });
  writeFileSync(artifactPath, `${JSON.stringify(billing, null, 2)}\n`, 'utf8');
  return artifactPath;
}
