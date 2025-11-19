import { Config } from "./config";

function ensureOk(res: Response) {
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
}

const normalizeBase = (url?: string) => {
  const trimmed = (url || Config.apiBase || "").trim();
  if (!trimmed) {
    throw new Error("Missing server URL");
  }
  return trimmed.replace(/\/$/, "");
};

const toAbsoluteUrl = (base: string, url?: string | null) => {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  if (url.startsWith("/")) return `${base}${url}`;
  return `${base}/${url}`;
};

const buildHeaders = (
  uploadKey?: string | null,
  extra?: Record<string, string>
): HeadersInit => {
  const headers: Record<string, string> = extra ? { ...extra } : {};
  if (uploadKey) {
    headers["X-Upload-Key"] = uploadKey;
  }
  return headers;
};

const buildDraftQuery = (
  filters?: DraftListFilters,
  pagination?: DraftListPagination
) => {
  const params = new URLSearchParams();
  if (filters?.status) {
    params.append("status", filters.status);
  }
  if (pagination?.limit != null) {
    params.append("limit", String(pagination.limit));
  }
  if (pagination?.offset != null) {
    params.append("offset", String(pagination.offset));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
};

export type UploadFileInput =
  | { uri: string; name: string; type: string }
  | { blob: Blob; name: string; type: string };

export type DraftStatus = "draft" | "ready" | "posted" | (string & {});

export async function uploadImages(
  serverBase: string | undefined,
  files: UploadFileInput[],
  metadata?: string,
  options?: RequestOptions
): Promise<{ item_id?: number }> {
  const base = normalizeBase(serverBase);
  const formData = buildUploadFormData(files, metadata);
  const res = await fetch(`${base}/api/upload`, {
    method: "POST",
    body: formData,
    headers: buildHeaders(options?.uploadKey),
  });
  ensureOk(res);
  return res.json();
}

export async function createDraftFromUpload(
  serverBase: string | undefined,
  files: UploadFileInput[],
  metadata?: string,
  options?: RequestOptions
): Promise<DraftDetail> {
  const base = normalizeBase(serverBase);
  const formData = buildUploadFormData(files, metadata);
  const res = await fetch(`${base}/api/drafts`, {
    method: "POST",
    body: formData,
    headers: buildHeaders(options?.uploadKey),
  });
  ensureOk(res);
  return res.json();
}

const buildUploadFormData = (
  files: UploadFileInput[],
  metadata?: string
) => {
  const formData = new FormData();
  files.forEach((file) => {
    if ("blob" in file) {
      formData.append("files", file.blob, file.name);
    } else {
      formData.append(
        "files",
        {
          uri: file.uri,
          name: file.name,
          type: file.type,
        } as any
      );
    }
  });
  if (metadata) {
    formData.append("metadata", metadata);
  }
  return formData;
};

type RequestOptions = {
  uploadKey?: string | null;
};

export type HealthResponse = {
  status?: string;
  version?: string;
  [key: string]: any;
};

export async function fetchHealth(
  serverBase: string | undefined,
  options?: RequestOptions
): Promise<HealthResponse> {
  const base = normalizeBase(serverBase);
  const res = await fetch(`${base}/health`, {
    headers: buildHeaders(options?.uploadKey),
  });
  ensureOk(res);
  return res.json();
}

export type DraftSummary = {
  id: number;
  title: string;
  status?: DraftStatus;
  brand?: string;
  size?: string;
  colour?: string;
  updated_at?: string;
  price_mid?: number;
  thumbnail_url?: string | null;
  photo_count?: number;
};

export type DraftPhoto = {
  id: number | string;
  url: string;
};

export type DraftDetail = DraftSummary & {
  description?: string;
  condition?: string;
  price_low?: number;
  price_high?: number;
  selected_price?: number;
  photos: DraftPhoto[];
  raw?: Record<string, any>;
};

export type DraftUpdatePayload = {
  title?: string;
  description?: string;
  price?: number;
  status?: string;
};

export type DraftListFilters = {
  status?: DraftStatus;
};

export type DraftListPagination = {
  limit?: number;
  offset?: number;
};

const resolveThumbnail = (row: any) => {
  if (row.thumbnail_url || row.thumbnail) return row.thumbnail_url || row.thumbnail;
  if (Array.isArray(row.photos) && row.photos.length > 0) {
    const first = row.photos[0];
    return (
      first.thumbnail_url ||
      first.url ||
      first.optimised_path ||
      first.original_path
    );
  }
  return row.attributes?.photos?.[0]?.url;
};

const normalizeDraftSummary = (row: any, base?: string): DraftSummary => {
  const thumbnail = resolveThumbnail(row);
  return {
    id: row.id ?? row.item_id ?? 0,
    title: row.title || `Draft #${row.id ?? row.item_id ?? "?"}`,
    status: row.status || row.attributes?.status || "draft",
    brand:
      row.brand?.value || row.brand || row.attributes?.brand?.value || undefined,
    size:
      row.size?.value || row.size || row.attributes?.size?.value || undefined,
    colour:
      row.colour?.value ||
      row.colour ||
      row.attributes?.colour?.value ||
      undefined,
    updated_at: row.updated_at || row.attributes?.updated_at,
    price_mid:
      row.price_mid ||
      row.recommended_pence ||
      row.prices?.mid ||
      row.prices?.recommended,
    thumbnail_url: thumbnail && base ? toAbsoluteUrl(base, thumbnail) : thumbnail,
    photo_count:
      row.photo_count ||
      (Array.isArray(row.photos) ? row.photos.length : undefined),
  };
};

export async function fetchDrafts(
  serverBase: string | undefined,
  options?: {
    filters?: DraftListFilters;
    pagination?: DraftListPagination;
  } & RequestOptions
): Promise<DraftSummary[]> {
  const base = normalizeBase(serverBase);
  const query = buildDraftQuery(options?.filters, options?.pagination);
  const res = await fetch(`${base}/api/drafts${query}`, {
    headers: buildHeaders(options?.uploadKey),
  });
  ensureOk(res);
  const data = await res.json();
  if (!Array.isArray(data)) {
    return [];
  }
  return data.map((row) => normalizeDraftSummary(row, base));
}

export async function fetchDraftDetail(
  serverBase: string | undefined,
  draftId: number,
  options?: RequestOptions
): Promise<DraftDetail> {
  const base = normalizeBase(serverBase);
  const res = await fetch(`${base}/api/drafts/${draftId}`, {
    headers: buildHeaders(options?.uploadKey),
  });
  ensureOk(res);
  const data = await res.json();
  const summary = normalizeDraftSummary(data, base);
  const photos: DraftPhoto[] = Array.isArray(data.photos)
    ? data.photos
        .map((photo: any, idx: number) => {
          const abs = toAbsoluteUrl(
            base,
            photo.url || photo.optimised_path || photo.original_path
          );
          if (!abs) return null;
          return {
            id: photo.id ?? idx,
            url: abs,
          };
        })
        .filter(Boolean) as DraftPhoto[]
    : [];
  return {
    ...summary,
    description: data.description || data.attributes?.description,
    condition: data.condition || data.attributes?.condition?.value,
    price_low: data.prices?.low || data.price_low,
    price_high: data.prices?.high || data.price_high,
    selected_price:
      data.selected_price || data.prices?.selected || data.price_selected,
    photos,
    raw: data,
  };
}

export async function updateDraft(
  serverBase: string | undefined,
  draftId: number,
  payload: DraftUpdatePayload,
  options?: RequestOptions
): Promise<void> {
  const base = normalizeBase(serverBase);
  const res = await fetch(`${base}/api/drafts/${draftId}`, {
    method: "PUT",
    headers: buildHeaders(options?.uploadKey, {
      "Content-Type": "application/json",
    }),
    body: JSON.stringify(payload),
  });
  ensureOk(res);
}
