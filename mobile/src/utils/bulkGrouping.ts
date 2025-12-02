import { BulkUploadConfig } from "../config";

export type BulkAsset = {
  uri: string;
  name: string;
  type: string;
  creationTime?: number | null;
};

const ensureTimestamps = (assets: BulkAsset[]) => {
  const now = Date.now();
  return assets.map((asset, idx) => ({
    ...asset,
    creationTime:
      typeof asset.creationTime === "number" && asset.creationTime > 0
        ? asset.creationTime
        : now + idx,
  }));
};

const balanceIntoChunks = (items: BulkAsset[], maxPerChunk: number) => {
  if (!items.length) return [];
  const groupCount = Math.ceil(items.length / maxPerChunk);
  const baseSize = Math.floor(items.length / groupCount);
  const remainder = items.length - baseSize * groupCount;

  const chunks: BulkAsset[][] = [];
  let cursor = 0;
  for (let i = 0; i < groupCount; i += 1) {
    const size = i < remainder ? baseSize + 1 : baseSize;
    chunks.push(items.slice(cursor, cursor + size));
    cursor += size;
  }
  return chunks;
};

export const groupAssetsIntoItems = (
  assets: BulkAsset[],
  gapSeconds: number = BulkUploadConfig.BULK_TIME_GAP_SECONDS,
  maxPerDraft: number = BulkUploadConfig.GROUPING_MAX_PHOTOS_PER_ITEM
): BulkAsset[][] => {
  if (!assets.length) return [];
  const enriched = ensureTimestamps(assets).sort(
    (a, b) => (a.creationTime || 0) - (b.creationTime || 0)
  );
  const gapMs = gapSeconds * 1000;

  const sessions: BulkAsset[][] = [];
  let current: BulkAsset[] = [];

  for (const asset of enriched) {
    if (!current.length) {
      current.push(asset);
      continue;
    }
    const prev = current[current.length - 1];
    const diff = (asset.creationTime || 0) - (prev.creationTime || 0);
    // NOTE: Bulk grouping assumes a new item if the time gap between photos > gapSeconds.
    if (diff > gapMs) {
      sessions.push(current);
      current = [asset];
    } else {
      current.push(asset);
    }
  }
  if (current.length) {
    sessions.push(current);
  }

  const result: BulkAsset[][] = [];
  for (const session of sessions) {
    const balanced = balanceIntoChunks(session, maxPerDraft);
    result.push(...balanced);
  }
  return result;
};
