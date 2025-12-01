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

export const groupAssetsIntoItems = (
  assets: BulkAsset[],
  gapSeconds: number = BulkUploadConfig.BULK_TIME_GAP_SECONDS,
  maxPerDraft: number = BulkUploadConfig.MAX_PHOTOS_PER_DRAFT
): BulkAsset[][] => {
  if (!assets.length) return [];
  const enriched = ensureTimestamps(assets).sort(
    (a, b) => (a.creationTime || 0) - (b.creationTime || 0)
  );
  const gapMs = gapSeconds * 1000;

  const groups: BulkAsset[][] = [];
  let current: BulkAsset[] = [];

  for (const asset of enriched) {
    if (!current.length) {
      current.push(asset);
      continue;
    }
    const prev = current[current.length - 1];
    const diff = (asset.creationTime || 0) - (prev.creationTime || 0);
    if (diff > gapMs) {
      groups.push(current);
      current = [asset];
    } else {
      current.push(asset);
    }
  }
  if (current.length) {
    groups.push(current);
  }

  // Split oversized groups into chunks to respect maxPerDraft.
  const chunked: BulkAsset[][] = [];
  for (const group of groups) {
    if (group.length <= maxPerDraft) {
      chunked.push(group);
      continue;
    }
    for (let i = 0; i < group.length; i += maxPerDraft) {
      chunked.push(group.slice(i, i + maxPerDraft));
    }
  }
  return chunked;
};
