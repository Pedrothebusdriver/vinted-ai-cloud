import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { Alert } from "react-native";
import * as Api from "../../api";
import { UploadFileInput } from "../../api";
import { groupAssetsIntoItems } from "../../utils/bulkGrouping";
import { runSingleUpload } from "../UploadScreen";
import { View } from "react-native";

jest.mock("react-native/Libraries/Components/Switch/Switch", () => {
  const React = require("react");
  const { View } = require("react-native");
  return (props: any) => React.createElement(View, props);
});

jest.mock("../../state/ServerContext", () => ({
  useServer: () => ({
    baseUrl: "http://api.test",
    uploadKey: null,
    lastConnected: null,
    servers: [],
    setBaseUrl: jest.fn(),
    setUploadKey: jest.fn(),
    setLastConnected: jest.fn(),
    addServer: jest.fn(),
    selectServer: jest.fn(),
    hydrated: true,
  }),
}));

class MockFormData {
  static instances: MockFormData[] = [];
  appended: { key: string; value: any; filename?: string }[] = [];

  constructor() {
    MockFormData.instances.push(this);
  }

  append(key: string, value: any, filename?: string) {
    this.appended.push({ key, value, filename });
  }
}

describe("processImageToDraft", () => {
  const originalFormData = global.FormData;
  const originalFetch = global.fetch;
  const originalConsoleLog = console.log;

  beforeEach(() => {
    MockFormData.instances = [];
    (global as any).FormData = MockFormData as any;
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 123, photos: [] }),
    });
    console.log = jest.fn();
  });

  afterEach(() => {
    (global as any).FormData = originalFormData;
    (global as any).fetch = originalFetch;
    jest.clearAllMocks();
    console.log = originalConsoleLog;
  });

  it("sends all selected photos to /process_image", async () => {
    const files: UploadFileInput[] = [
      { uri: "file://one.jpg", name: "one.jpg", type: "image/jpeg" },
      { uri: "file://two.jpg", name: "two.jpg", type: "image/jpeg" },
      { uri: "file://three.jpg", name: "three.jpg", type: "image/jpeg" },
    ];

    await Api.processImageToDraft(
      "http://api.test",
      files,
      JSON.stringify({ brand: "TestBrand" })
    );

    const instance = MockFormData.instances[0];
    expect(instance).toBeDefined();
    expect(instance.appended.map((entry) => entry.key)).toEqual([
      "file",
      "files",
      "files",
      "files",
      "metadata",
    ]);
    const names = instance.appended
      .filter((entry) => entry.key !== "metadata")
      .map((entry) => entry.value.name);
    expect(names).toEqual(["one.jpg", "one.jpg", "two.jpg", "three.jpg"]);
    expect((global.fetch as any)).toHaveBeenCalledWith(
      "http://api.test/process_image",
      expect.objectContaining({
        method: "POST",
        body: expect.any(MockFormData),
      })
    );
    expect(console.log).toHaveBeenCalledWith(
      `[FlipLens] processImageToDraft sending ${files.length} photos`
    );
  });
});

describe("groupAssetsIntoItems", () => {
  it("groups assets by time gap and splits oversized groups", () => {
    const base = 1_000_000;
    const assets = [
      { uri: "1", name: "1.jpg", type: "image/jpeg", creationTime: base },
      { uri: "2", name: "2.jpg", type: "image/jpeg", creationTime: base + 10_000 },
      { uri: "3", name: "3.jpg", type: "image/jpeg", creationTime: base + 35_000 },
      { uri: "4", name: "4.jpg", type: "image/jpeg", creationTime: base + 40_000 },
      { uri: "5", name: "5.jpg", type: "image/jpeg", creationTime: base + 62_000 },
    ];

    const groups = groupAssetsIntoItems(assets, 20, 2);
    expect(groups.length).toBe(3);
    expect(groups[0].map((a) => a.uri)).toEqual(["1", "2"]);
    expect(groups[1].map((a) => a.uri)).toEqual(["3", "4"]);
    expect(groups[2].map((a) => a.uri)).toEqual(["5"]);
  });
});

describe("runSingleUpload (single upload)", () => {
  let mockedProcess: jest.SpyInstance;
  let alertSpy: jest.SpyInstance;

  beforeEach(() => {
    mockedProcess = jest.spyOn(Api, "processImageToDraft").mockResolvedValue({
      id: 42,
      title: "Draft",
      photos: [],
    } as any);
    alertSpy = jest.spyOn(Alert, "alert").mockImplementation(() => {});
  });

  afterEach(() => {
    mockedProcess.mockRestore();
    alertSpy.mockRestore();
    jest.clearAllMocks();
  });

  it("passes all selected assets to processImageToDraft", async () => {
    const assets = [
      { uri: "1", name: "1.jpg", type: "image/jpeg" },
      { uri: "2", name: "2.jpg", type: "image/jpeg" },
      { uri: "3", name: "3.jpg", type: "image/jpeg" },
      { uri: "4", name: "4.jpg", type: "image/jpeg" },
    ];
    const navigate = jest.fn();
    await runSingleUpload({
      baseUrl: "http://api.test",
      files: assets as any,
      metadataPayload: undefined,
      uploadKey: null,
      navigation: { navigate } as any,
      clearForm: jest.fn(),
      setStatus: jest.fn(),
      setError: jest.fn(),
      setPending: jest.fn(),
    });

    expect(Api.processImageToDraft).toHaveBeenCalled();
    const call = mockedProcess.mock.calls[0];
    expect(call[1]).toHaveLength(4);
  });
});
