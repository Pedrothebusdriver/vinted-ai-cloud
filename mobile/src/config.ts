const envBase =
  typeof globalThis !== "undefined"
    ? (globalThis as any)?.process?.env?.EXPO_PUBLIC_API_BASE ||
      (globalThis as any)?.process?.env?.API_BASE_URL
    : undefined;

export const Config = {
  apiBase: envBase || "http://192.168.0.21:10000",
  coreSchemaVersion:
    (typeof globalThis !== "undefined"
      ? (globalThis as any)?.process?.env?.EXPO_PUBLIC_CORE_VERSION
      : undefined) || "0.1.0",
};

export const BulkUploadConfig = {
  BULK_TIME_GAP_SECONDS: 90,
  MAX_PHOTOS_PER_DRAFT: 8,
  MAX_BULK_PHOTOS: 80,
  INTER_REQUEST_DELAY_MS: 250,
};
