const DEFAULT_API_VERSION = 'v1';

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '');
}

function normalizePathSegments(pathname: string): string[] {
  return pathname.split('/').filter(Boolean);
}

function serializeUrlWithoutTrailingSlash(url: URL): string {
  return trimTrailingSlashes(url.toString());
}

export function normalizeVersionedApiBaseUrl(
  apiBaseUrl: string | undefined,
  apiVersion: string = DEFAULT_API_VERSION,
): string | undefined {
  const trimmed = apiBaseUrl?.trim();
  if (!trimmed) {
    return undefined;
  }

  try {
    const url = new URL(trimmed);
    const segments = normalizePathSegments(url.pathname);
    const lastSegment = segments[segments.length - 1]?.toLowerCase();
    if (lastSegment !== apiVersion.toLowerCase()) {
      segments.push(apiVersion);
    }
    url.pathname = segments.length > 0 ? `/${segments.join('/')}` : `/${apiVersion}`;
    return serializeUrlWithoutTrailingSlash(url);
  } catch {
    const cleanBase = trimTrailingSlashes(trimmed);
    return cleanBase.toLowerCase().endsWith(`/${apiVersion.toLowerCase()}`)
      ? cleanBase
      : `${cleanBase}/${apiVersion}`;
  }
}

export function removeTrailingApiVersion(
  apiBaseUrl: string | undefined,
  apiVersion: string = DEFAULT_API_VERSION,
): string | undefined {
  const trimmed = apiBaseUrl?.trim();
  if (!trimmed) {
    return undefined;
  }

  try {
    const url = new URL(trimmed);
    const segments = normalizePathSegments(url.pathname);
    const lastSegment = segments[segments.length - 1]?.toLowerCase();
    if (lastSegment === apiVersion.toLowerCase()) {
      segments.pop();
      url.pathname = segments.length > 0 ? `/${segments.join('/')}` : '/';
    }
    return serializeUrlWithoutTrailingSlash(url);
  } catch {
    const cleanBase = trimTrailingSlashes(trimmed);
    return cleanBase.toLowerCase().endsWith(`/${apiVersion.toLowerCase()}`)
      ? cleanBase.slice(0, -apiVersion.length - 1) || undefined
      : cleanBase;
  }
}
