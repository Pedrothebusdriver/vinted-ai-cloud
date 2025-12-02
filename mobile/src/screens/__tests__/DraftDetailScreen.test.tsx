import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { DraftDetailScreen } from "../DraftDetailScreen";
import * as Api from "../../api";

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

jest.mock("../../api", () => {
  const actual = jest.requireActual("../../api");
  return {
    ...actual,
    fetchDraftDetail: jest.fn(),
    updateDraft: jest.fn(),
  };
});

const mockDraft = {
  id: 1,
  title: "Draft",
  brand: "Nike",
  size: "M",
  colour: "Black",
  condition: "good",
  photos: [],
};

describe("DraftDetailScreen", () => {
  beforeEach(() => {
    jest.spyOn(Api, "fetchDraftDetail").mockResolvedValue(mockDraft as any);
    jest.spyOn(Api, "updateDraft").mockResolvedValue(undefined as any);
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("renders editable brand/size/colour/condition fields", async () => {
    const { findByPlaceholderText } = render(
      <DraftDetailScreen
        navigation={{ navigate: jest.fn() } as any}
        route={{ key: "DraftDetail", name: "DraftDetail", params: { id: 1 } } as any}
      />
    );

    expect(await findByPlaceholderText("Zara / Nike")).toBeTruthy();
    expect(await findByPlaceholderText("M / UK 10")).toBeTruthy();
    expect(await findByPlaceholderText("Charcoal")).toBeTruthy();
  });

  it("saves updated fields", async () => {
    const { findByDisplayValue, findByText } = render(
      <DraftDetailScreen
        navigation={{ navigate: jest.fn() } as any}
        route={{ key: "DraftDetail", name: "DraftDetail", params: { id: 1 } } as any}
      />
    );

    const brandInput = await findByDisplayValue("Nike");
    fireEvent.changeText(brandInput, "Adidas");
    await waitFor(() => {
      expect((brandInput as any).props.value).toBe("Adidas");
    });
    const colourInput = await findByDisplayValue("Black");
    fireEvent.changeText(colourInput, "Blue");

    const saveButton = await findByText("Save changes");
    fireEvent.press(saveButton);

    await waitFor(() => {
      expect(Api.updateDraft).toHaveBeenCalled();
    });
    const call = (Api.updateDraft as jest.Mock).mock.calls[0][2];
    expect(call.brand).toBe("Adidas");
    expect(call.colour).toBe("Blue");
  });
});
