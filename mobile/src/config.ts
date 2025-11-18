const envBase =
  typeof globalThis !== "undefined"
    ? (globalThis as any)?.process?.env?.EXPO_PUBLIC_API_BASE ||
      (globalThis as any)?.process?.env?.API_BASE_URL
    : undefined;

export const Config = {
  apiBase: envBase || "http://192.168.0.10:8000",
};
