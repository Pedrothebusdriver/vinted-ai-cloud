import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { ConnectScreen } from "../ConnectScreen";
import { Config } from "../../config";
import { useServer } from "../../state/ServerContext";

jest.mock("../../state/ServerContext", () => ({
  useServer: jest.fn(),
}));

const mockedUseServer = useServer as jest.MockedFunction<typeof useServer>;
const originalFetch = global.fetch;

const createNavigation = () =>
  ({
    navigate: jest.fn(),
  } as any);

const createRoute = () =>
  ({
    key: "test-connect",
    name: "Connect",
  } as any);

const buildServerContext = (overrides = {}) => ({
  baseUrl: Config.apiBase,
  uploadKey: null,
  lastConnected: null,
  servers: [],
  hydrated: true,
  setBaseUrl: jest.fn(),
  setUploadKey: jest.fn(),
  setLastConnected: jest.fn(),
  addServer: jest.fn(),
  selectServer: jest.fn(),
  ...overrides,
});

const escapeRegex = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("ConnectScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseServer.mockReturnValue(buildServerContext());
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders the input with the default value from Config.apiBase", () => {
    const { getByDisplayValue } = render(
      <ConnectScreen navigation={createNavigation()} route={createRoute()} />
    );

    expect(getByDisplayValue(Config.apiBase)).toBeTruthy();
  });

  it("calls fetch with the /health path and surfaces the tested URL on success", async () => {
    const baseUrl = "http://demo.local:1234/";
    const normalized = "http://demo.local:1234";
    const testedUrl = `${normalized}/health`;

    mockedUseServer.mockReturnValue(
      buildServerContext({
        baseUrl,
      })
    );

    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: "2.0.0" }),
    });
    global.fetch = fetchMock as any;

    const { getByText, findByText } = render(
      <ConnectScreen navigation={createNavigation()} route={createRoute()} />
    );

    fireEvent.press(getByText("Test Connection"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith(testedUrl);

    const message = await findByText(new RegExp(escapeRegex(testedUrl)));
    expect(message).toBeTruthy();
  });
});
