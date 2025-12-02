import { groupAssetsIntoItems } from "../bulkGrouping";

const buildAssets = (count: number, start: number = Date.now()) =>
  Array.from({ length: count }).map((_, idx) => ({
    uri: `file://${idx + 1}.jpg`,
    name: `${idx + 1}.jpg`,
    type: "image/jpeg",
    creationTime: start + idx * 1000,
  }));

describe("groupAssetsIntoItems", () => {
  it("splits a flat batch into balanced groups without dropping photos", () => {
    const assets = buildAssets(10, 1_000);
    const groups = groupAssetsIntoItems(assets, 999, 4);
    const lengths = groups.map((g) => g.length);
    expect(lengths).toEqual([4, 3, 3]);
    expect(groups.flat().length).toBe(10);
  });

  it("honours gaps by starting a new session", () => {
    const first = buildAssets(3, 1_000);
    const second = buildAssets(2, 300_000); // 5 minutes later
    const groups = groupAssetsIntoItems([...first, ...second], 20, 8);
    expect(groups).toHaveLength(2);
    expect(groups[0]).toHaveLength(3);
    expect(groups[1]).toHaveLength(2);
  });
});
