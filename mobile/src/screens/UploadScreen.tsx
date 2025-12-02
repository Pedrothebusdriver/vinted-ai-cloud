import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  Switch,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  processImageToDraft,
  UploadFileInput,
  DraftDetail,
} from "../api";
import { BulkUploadConfig } from "../config";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";
import { groupAssetsIntoItems } from "../utils/bulkGrouping";
import { colors, radius, shadows, spacing } from "../theme/tokens";
import { ui } from "../theme/components";

type Props = NativeStackScreenProps<RootStackParamList, "Upload"> & {
  initialAssets?: LocalAsset[];
};

type LocalAsset = {
  uri: string;
  name?: string;
  type?: string;
  creationTime?: number | null;
};

type BulkHistoryEntry = {
  timestamp: number;
  drafts: { id: string | number; title?: string | null; price_low?: number; price_high?: number; price_mid?: number }[];
  groups: number[];
};

type SingleUploadDeps = {
  baseUrl?: string | null;
  files: UploadFileInput[];
  metadataPayload?: string;
  uploadKey?: string | null;
  navigation: Props["navigation"];
  clearForm: () => void;
  setStatus: (value: string | null) => void;
  setError: (value: string | null) => void;
  setPending: (value: boolean) => void;
};

export async function runSingleUpload({
  baseUrl,
  files,
  metadataPayload,
  uploadKey,
  navigation,
  clearForm,
  setStatus,
  setError,
  setPending,
}: SingleUploadDeps) {
  setPending(true);
  setStatus(null);
  setError(null);
  try {
    const response: any = await processImageToDraft(
      baseUrl || undefined,
      files,
      metadataPayload,
      { uploadKey }
    );
    const newId =
      response?.id ??
      response?.draft_id ??
      response?.item_id ??
      response?.draft?.id;
    setStatus("Draft created. Opening editor...");
    if (newId) {
      navigation.navigate("DraftDetail", { id: newId });
      clearForm();
    } else {
      Alert.alert(
        "Uploaded",
        "Draft created. Refresh the Drafts list to see it."
      );
    }
  } catch (err: any) {
    const message = err?.message || "Unable to upload photos.";
    setError(message);
    Alert.alert("Upload failed", message);
  } finally {
    setPending(false);
  }
}

export const UploadScreen = ({ navigation, initialAssets }: Props) => {
  const { baseUrl, uploadKey } = useServer();
  const [assets, setAssets] = useState<LocalAsset[]>(initialAssets || []);
  const [brand, setBrand] = useState("");
  const [size, setSize] = useState("");
  const [condition, setCondition] = useState("good");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [bulkMode, setBulkMode] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{
    current: number;
    total: number;
  } | null>(null);
  const [bulkSummary, setBulkSummary] = useState<string | null>(null);
  const [bulkRecap, setBulkRecap] = useState<
    { id: string | number; title?: string | null; price_low?: number; price_high?: number; price_mid?: number }[] | null
  >(null);
  const [bulkHistory, setBulkHistory] = useState<BulkHistoryEntry[]>([]);

  const files = useMemo<UploadFileInput[]>(
    () =>
      assets.map((asset, idx) => ({
        uri: asset.uri,
        name: asset.name || `photo-${idx + 1}.jpg`,
        type: asset.type || "image/jpeg",
      })),
    [assets]
  );

  const groupedDrafts = useMemo(
    () =>
      groupAssetsIntoItems(
        assets.map((asset, idx) => ({
          uri: asset.uri,
          name: asset.name || `photo-${idx + 1}.jpg`,
          type: asset.type || "image/jpeg",
          creationTime: asset.creationTime ?? null,
        })),
        BulkUploadConfig.BULK_TIME_GAP_SECONDS,
        BulkUploadConfig.GROUPING_MAX_PHOTOS_PER_ITEM
      ),
    [assets]
  );

  useEffect(() => {
    if (__DEV__) {
      const summary = groupedDrafts.map((g) => g.length).join(", ") || "none";
      // eslint-disable-next-line no-console
      console.log(`[BulkGrouping] assets=${assets.length} groups=[${summary}]`);
    }
  }, [assets.length, groupedDrafts]);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const raw = await AsyncStorage.getItem("bulk_upload_history_v1");
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setBulkHistory(parsed);
        }
      } catch (err) {
        console.warn("bulk_history_load_failed", err);
      }
    };
    loadHistory();
  }, []);

  const openDraft = useCallback(
    (id: string | number) => {
      const numeric = Number(id);
      if (!Number.isNaN(numeric)) {
        navigation.navigate("DraftDetail", { id: numeric });
      } else {
        navigation.navigate("Drafts");
      }
    },
    [navigation]
  );

  const renderPriceRange = useCallback(
    (draft: { price_low?: number; price_high?: number; price_mid?: number }) => {
      if (typeof draft.price_low === "number" && typeof draft.price_high === "number") {
        return `£${draft.price_low}-${draft.price_high}`;
      }
      if (typeof draft.price_mid === "number") {
        return `£${draft.price_mid}`;
      }
      return "Price TBD";
    },
    []
  );

  const persistHistory = useCallback(
    async (entry: BulkHistoryEntry) => {
      try {
        const next = [entry, ...bulkHistory].slice(0, 5);
        setBulkHistory(next);
        await AsyncStorage.setItem("bulk_upload_history_v1", JSON.stringify(next));
      } catch (err) {
        console.warn("bulk_history_save_failed", err);
      }
    },
    [bulkHistory]
  );

  const formatTimestamp = useCallback((ts: number) => {
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return String(ts);
    }
  }, []);

  const requestMediaPermission = useCallback(async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permission needed", "Allow photo access to upload.");
      return false;
    }
    return true;
  }, []);

  const pickImages = useCallback(async () => {
    const allowed = await requestMediaPermission();
    if (!allowed) return;
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.8,
    });
    if (!result.canceled) {
      const picked = result.assets.map((asset) => ({
        uri: asset.uri,
        name: asset.fileName || asset.assetId || asset.uri.split("/").pop(),
        type: asset.mimeType || "image/jpeg",
        creationTime: (asset as any).creationTime ?? null,
      }));
      setAssets((prev) => {
        const merged = [...prev, ...picked];
        if (bulkMode && merged.length > BulkUploadConfig.MAX_BULK_PHOTOS) {
          Alert.alert(
            "Too many photos",
            `Bulk upload is limited to ${BulkUploadConfig.MAX_BULK_PHOTOS} photos. We kept the first ${BulkUploadConfig.MAX_BULK_PHOTOS}.`
          );
          return merged.slice(0, BulkUploadConfig.MAX_BULK_PHOTOS);
        }
        return merged;
      });
    }
  }, [bulkMode, requestMediaPermission]);

  const takePhoto = useCallback(async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Camera access needed", "Allow camera access to take photos.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });
    if (!result.canceled && result.assets.length > 0) {
      const asset = result.assets[0];
      const picked = {
        uri: asset.uri,
        name: asset.fileName || asset.assetId || asset.uri.split("/").pop(),
        type: asset.mimeType || "image/jpeg",
        creationTime: (asset as any).creationTime ?? null,
      };
      setAssets((prev) => {
        const merged = [...prev, picked];
        if (bulkMode && merged.length > BulkUploadConfig.MAX_BULK_PHOTOS) {
          Alert.alert(
            "Too many photos",
            `Bulk upload is limited to ${BulkUploadConfig.MAX_BULK_PHOTOS} photos. We kept the first ${BulkUploadConfig.MAX_BULK_PHOTOS}.`
          );
          return merged.slice(0, BulkUploadConfig.MAX_BULK_PHOTOS);
        }
        return merged;
      });
    }
  }, [bulkMode]);

  const clearForm = useCallback(() => {
    setAssets([]);
    setBrand("");
    setSize("");
    setCondition("good");
    setStatus(null);
    setError(null);
    setBulkProgress(null);
    setBulkSummary(null);
  }, []);

  const metadataPayload = useMemo(() => {
    const payload: Record<string, string> = {};
    if (brand.trim()) payload.brand = brand.trim();
    if (size.trim()) payload.size = size.trim();
    if (condition.trim()) payload.condition = condition.trim();
    return Object.keys(payload).length ? JSON.stringify(payload) : undefined;
  }, [brand, condition, size]);

  const onUpload = useCallback(async () => {
    if (!files.length) {
      Alert.alert("Add photos", "Select at least one photo to upload.");
      return;
    }
    if (!baseUrl?.trim()) {
      Alert.alert("Connect to server", "Add the server URL on the Connect tab first.");
      return;
    }
    if (bulkMode) {
      setBulkSummary(null);
      setBulkRecap(null);
      setError(null);
      setStatus(null);
      setPending(true);
      const groups = groupedDrafts;
      if (!groups.length) {
        Alert.alert("No groups", "Could not group these photos. Try again.");
        setPending(false);
        return;
      }
      let success = 0;
      let failures = 0;
      const createdDrafts: {
        id: string | number;
        title?: string | null;
        price_low?: number;
        price_mid?: number;
        price_high?: number;
      }[] = [];
      try {
        for (let i = 0; i < groups.length; i += 1) {
          setBulkProgress({ current: i + 1, total: groups.length });
          const group = groups[i];
          const payload: UploadFileInput[] = group.map((asset, idx) => ({
            uri: asset.uri,
            name: asset.name || `photo-${idx + 1}.jpg`,
            type: asset.type || "image/jpeg",
          }));
          try {
            const response: any = await processImageToDraft(baseUrl, payload, metadataPayload, {
              uploadKey,
            });
            success += 1;
            if (response) {
              createdDrafts.push({
                id:
                  response.id ||
                  response.draft_id ||
                  response.item_id ||
                  response.draft?.id ||
                  `draft-${i + 1}`,
                title: response.title,
                price_low: response.price_low,
                price_mid: response.price_mid,
                price_high: response.price_high,
              });
            }
          } catch (err) {
            console.error("bulk_upload_failed", err);
            failures += 1;
          }
          if (i < groups.length - 1 && BulkUploadConfig.INTER_REQUEST_DELAY_MS > 0) {
            await new Promise((resolve) =>
              setTimeout(resolve, BulkUploadConfig.INTER_REQUEST_DELAY_MS)
            );
          }
        }
        const summary = failures
          ? `Created ${success} drafts, ${failures} failed.`
          : `Created ${success} drafts.`;
        setBulkSummary(summary);
        if (createdDrafts.length) {
          setBulkRecap(createdDrafts);
          await persistHistory({
            timestamp: Date.now(),
            drafts: createdDrafts,
            groups: groupedDrafts.map((g) => g.length),
          });
        }
        if (failures) {
          Alert.alert("Bulk upload partial", summary);
        }
      } finally {
        setPending(false);
        setBulkProgress(null);
      }
      return;
    }

    await runSingleUpload({
      baseUrl,
      files,
      metadataPayload,
      uploadKey,
      navigation,
      clearForm,
      setStatus,
      setError,
      setPending,
    });
  }, [
    baseUrl,
    bulkMode,
    clearForm,
    files,
    groupedDrafts,
    metadataPayload,
    navigation,
    persistHistory,
    uploadKey,
  ]);

  return (
    <SafeAreaView style={ui.screen}>
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[styles.container, { paddingBottom: spacing.xxl }]}
      >
        <Text style={styles.heading}>Upload new item</Text>
        <Text style={styles.description}>
          Choose photos, then send them to your FlipLens backend. We&apos;ll
          include your upload key automatically.
        </Text>
        {bulkRecap?.length ? (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Last bulk upload</Text>
            <Text style={styles.helper}>
              Created {bulkRecap.length} draft{bulkRecap.length === 1 ? "" : "s"}.
            </Text>
            {bulkRecap.slice(0, 4).map((draft, idx) => (
              <View style={styles.recapRow} key={`${draft.id}-${idx}`}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.recapTitle} numberOfLines={1}>
                    {draft.title || `Draft ${draft.id}`}
                  </Text>
                  <Text style={styles.recapMeta}>{renderPriceRange(draft)}</Text>
                </View>
                <TouchableOpacity
                  style={styles.recapButton}
                  onPress={() => openDraft(draft.id)}
                >
                  <Text style={styles.recapButtonText}>Edit</Text>
                </TouchableOpacity>
              </View>
            ))}
            <TouchableOpacity
              style={[styles.secondaryButton, { marginTop: spacing.xs }]}
              onPress={() => navigation.navigate("Drafts")}
            >
              <Text style={styles.secondaryButtonText}>Open drafts list</Text>
            </TouchableOpacity>
          </View>
        ) : null}
        {bulkHistory.length ? (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Recent bulk uploads</Text>
            {bulkHistory.slice(0, 3).map((entry, idx) => (
              <View key={`${entry.timestamp}-${idx}`} style={styles.recapRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.recapTitle}>
                    {formatTimestamp(entry.timestamp)}
                  </Text>
                  <Text style={styles.recapMeta}>
                    Drafts: {entry.drafts.length} · Groups: {entry.groups.join(" / ")}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.recapButton}
                  onPress={() => navigation.navigate("Drafts")}
                >
                  <Text style={styles.recapButtonText}>View</Text>
                </TouchableOpacity>
              </View>
            ))}
          </View>
        ) : null}

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Photos</Text>
          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={[styles.primaryButton, pending && styles.disabledButton]}
              onPress={pickImages}
              disabled={pending}
            >
              <Text style={styles.primaryButtonText}>Select photos</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.secondaryButton, pending && styles.disabledButton]}
              onPress={takePhoto}
              disabled={pending}
            >
              <Text style={styles.secondaryButtonText}>Take photo</Text>
            </TouchableOpacity>
          </View>
          {assets.length > 0 ? (
            <>
              <View style={styles.previewGrid}>
                {assets.map((asset) => (
                  <Image
                    key={asset.uri}
                    source={{ uri: asset.uri }}
                    style={styles.preview}
                  />
                ))}
              </View>
              <Text style={styles.helper}>
                {assets.length} photo{assets.length === 1 ? "" : "s"} selected. Grouping preview:{" "}
                {groupedDrafts.map((g) => g.length).join(" / ") || "-"}
              </Text>
            </>
          ) : (
            <View style={styles.placeholder}>
              <Text style={styles.placeholderText}>
                No photos selected yet. Add a few shots to create a draft.
              </Text>
            </View>
          )}
        </View>

        <View style={styles.card}>
          <View style={styles.bulkToggleRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>Bulk upload</Text>
              <Text style={styles.helper}>
                Group photos into multiple drafts automatically.
              </Text>
            </View>
            <Switch
              value={bulkMode}
              onValueChange={setBulkMode}
              disabled={pending}
            />
          </View>
          {bulkMode && assets.length > 0 && (
            <View style={styles.helperCard}>
              <Text style={styles.helper}>
                Estimated drafts: {groupedDrafts.length} (up to{" "}
                {BulkUploadConfig.GROUPING_MAX_PHOTOS_PER_ITEM} similar photos per draft).
              </Text>
              {/* NOTE: Bulk grouping clusters visually similar photos together when enabled. */}
            </View>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Metadata (optional)</Text>
          <View style={styles.field}>
            <Text style={styles.label}>Brand</Text>
            <TextInput
              style={styles.input}
              value={brand}
              onChangeText={setBrand}
              placeholder="Nike"
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.label}>Size</Text>
            <TextInput
              style={styles.input}
              value={size}
              onChangeText={setSize}
              placeholder="M / UK 10 / W32"
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.label}>Condition</Text>
            <View style={styles.chipRow}>
              {CONDITION_OPTIONS.map((option) => (
                <TouchableOpacity
                  key={option.value}
                  style={[
                    styles.chip,
                    condition === option.value && styles.chipActive,
                  ]}
                  onPress={() => setCondition(option.value)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      condition === option.value && styles.chipTextActive,
                    ]}
                  >
                    {option.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={styles.helper}>
              These values get sent to the draft builder as JSON metadata.
            </Text>
          </View>
        </View>

        {pending && <ActivityIndicator style={{ marginBottom: spacing.sm }} />}
        {error && <Text style={styles.error}>{error}</Text>}
        {status && <Text style={styles.status}>{status}</Text>}
        {bulkProgress && (
          <Text style={styles.status}>
            Creating drafts {bulkProgress.current} / {bulkProgress.total}...
          </Text>
        )}
        {bulkSummary && <Text style={styles.status}>{bulkSummary}</Text>}

        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[
              styles.primaryButton,
              (pending || files.length === 0) && styles.disabledButton,
            ]}
            onPress={onUpload}
            disabled={pending || files.length === 0}
          >
            <Text style={styles.primaryButtonText}>
              {pending ? "Uploading..." : "Upload"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={clearForm}
            disabled={!assets.length && !brand && !size}
          >
            <Text style={styles.secondaryButtonText}>Clear</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const CONDITION_OPTIONS = [
  { label: "New", value: "new" },
  { label: "Excellent", value: "excellent" },
  { label: "Good", value: "good" },
  { label: "Fair", value: "fair" },
];

const styles = StyleSheet.create({
  container: {
    padding: spacing.xl,
    gap: spacing.lg,
    backgroundColor: colors.background,
  },
  heading: { ...ui.heading },
  description: { ...ui.subheading },
  card: {
    ...ui.card,
    gap: spacing.md,
  },
  sectionTitle: { ...ui.heading },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  primaryButton: {
    ...ui.primaryButton,
    flex: 1,
  },
  primaryButtonText: { ...ui.primaryButtonText },
  secondaryButton: {
    ...ui.secondaryButton,
    flex: 1,
  },
  secondaryButtonText: { ...ui.secondaryButtonText },
  disabledButton: {
    opacity: 0.65,
  },
  previewGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  preview: {
    width: 110,
    height: 140,
    borderRadius: radius.md,
  },
  placeholder: {
    ...ui.card,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderText: {
    color: colors.muted,
    textAlign: "center",
  },
  recapRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  recapTitle: {
    fontWeight: "700",
    color: colors.text,
  },
  recapMeta: {
    color: colors.muted,
  },
  field: {
    gap: spacing.xs,
  },
  label: { ...ui.label },
  input: {
    ...ui.input,
  },
  helper: { ...ui.helper },
  status: {
    color: colors.success,
    backgroundColor: "#ecfdf3",
    padding: spacing.sm,
    borderRadius: radius.md,
  },
  error: {
    color: colors.danger,
    backgroundColor: "#fef2f2",
    padding: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "#fecdd3",
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.card,
  },
  chipActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  chipText: {
    color: colors.text,
    fontWeight: "600",
  },
  chipTextActive: {
    color: "#fff",
  },
  recapButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.card,
  },
  recapButtonText: {
    color: colors.accent,
    fontWeight: "700",
  },
  bulkToggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  helperCard: {
    backgroundColor: colors.background,
    borderRadius: radius.md,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
