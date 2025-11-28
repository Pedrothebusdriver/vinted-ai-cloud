import { normalizeBaseUrl } from "../ConnectScreen";

describe("normalizeBaseUrl", () => {
  it("trims a trailing slash", () => {
    expect(normalizeBaseUrl("http://example.com/")).toBe("http://example.com");
  });

  it("adds http:// when the protocol is missing", () => {
    expect(normalizeBaseUrl("example.com")).toBe("http://example.com");
  });

  it("throws on an empty string", () => {
    expect(() => normalizeBaseUrl("   ")).toThrow("Missing server URL");
  });
});
