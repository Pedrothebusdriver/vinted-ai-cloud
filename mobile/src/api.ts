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

export type UploadFileInput =
  | { uri: string; name: string; type: string }
  | { blob: Blob; name: string; type: string };

export async function uploadImages(
  serverBase: string | undefined,
  files: UploadFileInput[],
  metadata?: string
): Promise<{ item_id: number }> {
  const base = normalizeBase(serverBase);
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
  const res = await fetch(`${base}/api/upload`, {
    method: "POST",
    body: formData,
  });
  ensureOk(res);
  return res.json();
}

export type HealthResponse = {
  status?: string;
  version?: string;
  [key: string]: any;
};

export async function fetchHealth(
  serverBase: string | undefined
): Promise<HealthResponse> {
  const base = normalizeBase(serverBase);
  const res = await fetch(`${base}/health`);
  ensureOk(res);
  return res.json();
}

export type DraftSummary = {
  id: number;
  title: string;
  status?: string;
  brand?: string;
  size?: string;
  colour?: string;
  updated_at?: string;
  price_mid?: number;
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

const normalizeDraftSummary = (row: any): DraftSummary => ({
  id: row.id ?? row.item_id ?? 0,
  title: row.title || `Draft #${row.id ?? row.item_id ?? "?"}`,
  status: row.status || row.attributes?.status || "draft",
  brand:
    row.brand?.value || row.brand || row.attributes?.brand?.value || undefined,
  size:
    row.size?.value || row.size || row.attributes?.size?.value || undefined,
  colour:
    row.colour?.value || row.colour || row.attributes?.colour?.value || undefined,
  updated_at: row.updated_at || row.attributes?.updated_at,
  price_mid:
    row.price_mid ||
    row.recommended_pence ||
    row.prices?.mid ||
    row.prices?.recommended,
});

export async function fetchDrafts(
  serverBase: string | undefined
): Promise<DraftSummary[]> {
  const base = normalizeBase(serverBase);
  const res = await fetch(`${base}/api/drafts`);
  ensureOk(res);
  const data = await res.json();
  if (!Array.isArray(data)) {
    return [];
  }
  return data.map((row) => normalizeDraftSummary(row));
}

export async function fetchDraftDetail(
  serverBase: string | undefined,
  draftId: number
): Promise<DraftDetail> {
  const base = normalizeBase(serverBase);
  const res = await fetch(`${base}/api/drafts/${draftId}`);
  if (!res.ok) {
    throw new Error(`Unable to load draft ${draftId}`);
  }
  const data = await res.json();
  const summary = normalizeDraftSummary(data);
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
  payload: DraftUpdatePayload
): Promise<void> {
  const base = normalizeBase(serverBase);
  try {
    const res = await fetch(`${base}/api/drafts/${draftId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Update failed: ${res.status}`);
    }
  } catch (error) {
    console.warn("draft_update_failed", error);
  }
}
