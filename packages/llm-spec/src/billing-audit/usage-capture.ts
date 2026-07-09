import type { UsageCaptureRecord } from './type';
import { getUnixTimeSeconds, writeUsageArtifact } from './write-usage-artifact';

const usageCaptures: UsageCaptureRecord[] = [];
let usageCaptureStartTime: string | undefined;

export function isUsageCaptureEnabled(): boolean {
  const value = process.env.BILLING_AUDIT_USAGE_CAPTURE?.trim().toLowerCase();
  return value === '1' || value === 'true' || value === 'yes' || value === 'on';
}

export function clearUsageCaptures(): void {
  usageCaptures.length = 0;
  usageCaptureStartTime = getUnixTimeSeconds();
}

export function recordUsageCapture(record: UsageCaptureRecord): void {
  if (!isUsageCaptureEnabled()) {
    return;
  }
  usageCaptures.push(record);
}

export function getUsageCaptures(): UsageCaptureRecord[] {
  return [...usageCaptures];
}

export function flushUsageCaptures(path?: string): string | undefined {
  if (usageCaptures.length === 0) {
    return undefined;
  }
  return writeUsageArtifact(
    {
      startTime: usageCaptureStartTime ?? getUnixTimeSeconds(),
      endTime: getUnixTimeSeconds(),
      records: getUsageCaptures(),
    },
    path,
  );
}
