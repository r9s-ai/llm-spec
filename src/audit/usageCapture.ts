import type { UsageCaptureRecord } from './type';
import { getUnixTimeSeconds, writeUsageArtifact } from './writeUsageArtifact';

const usageCaptures: UsageCaptureRecord[] = [];
let usageCaptureStartTime: string | undefined;

export function clearUsageCaptures(): void {
  usageCaptures.length = 0;
  usageCaptureStartTime = getUnixTimeSeconds();
}

export function recordUsageCapture(record: UsageCaptureRecord): void {
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
