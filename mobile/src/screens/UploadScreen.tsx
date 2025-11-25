import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import {
  createDraftFromUpload,
  UploadFileInput,
  DraftDetail,
} from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Upload">;

type LocalAsset = {
  uri: string;
  name?: string;
  type?: string;
};

export const UploadScreen = ({ navigation }: Props) => {
  const { baseUrl, uploadKey } = useServer();
  const [assets, setAssets] = useState<LocalAsset[]>([]);
  const [brand, setBrand] = useState("");
  const [size, setSize] = useState("");
  const [condition, setCondition] = useState("good");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const files = useMemo<UploadFileInput[]>(
    () =>
      assets.map((asset, idx) => ({
        uri: asset.uri,
        name: asset.name || `photo-${idx + 1}.jpg`,
        type: asset.type || "image/jpeg",
      })),
    [assets]
  );

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
      setAssets((prev) => [
        ...prev,
        ...result.assets.map((asset) => ({
          uri: asset.uri,
          name: asset.fileName || asset.assetId || asset.uri.split("/").pop(),
          type: asset.mimeType || "image/jpeg",
        })),
      ]);
    }
  }, [requestMediaPermission]);

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
      setAssets((prev) => [
        ...prev,
        {
          uri: asset.uri,
          name: asset.fileName || asset.assetId || asset.uri.split("/").pop(),
          type: asset.mimeType || "image/jpeg",
        },
      ]);
    }
  }, []);

  const clearForm = useCallback(() => {
    setAssets([]);
    setBrand("");
    setSize("");
    setCondition("good");
    setStatus(null);
    setError(null);
  }, []);

  const metadataPayload = useMemo(() => {
    const payload: Record<string, string> = {};
    if (brand.trim()) payload.brand = brand.trim();
    if (size.trim()) payload.size = size.trim();
    if (condition.trim()) payload.condition = condition.trim();
    return Object.keys(payload).length ? JSON.stringify(payload) : undefined;
  }, [brand, condition, size]);

  const extractDraftId = (response: DraftDetail | any) => {
    if (!response) return undefined;
    return (
      response.id ??
      response.draft_id ??
      response.item_id ??
      response.draft?.id
    );
  };

  const onUpload = useCallback(async () => {
    if (!files.length) {
      Alert.alert("Add photos", "Select at least one photo to upload.");
      return;
    }
    if (!baseUrl?.trim()) {
      Alert.alert("Connect to server", "Add the server URL on the Connect tab first.");
      return;
    }
    setPending(true);
    setStatus(null);
    setError(null);
    try {
      const response = await createDraftFromUpload(
        baseUrl,
        files,
        metadataPayload,
        { uploadKey }
      );
      const newId = extractDraftId(response);
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
  }, [
    baseUrl,
    clearForm,
    files,
    metadataPayload,
    navigation,
    uploadKey,
  ]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Upload photos</Text>
        <Text style={styles.description}>
          Select photos and send them to{" "}
          <Text style={styles.code}>POST /api/drafts</Text>. We&apos;ll send the
          stored upload key automatically.
        </Text>
        <View style={styles.buttonRow}>
          <Button title="Pick from library" onPress={pickImages} />
          <Button title="Take photo" onPress={takePhoto} />
        </View>
        {assets.length > 0 ? (
          <ScrollView horizontal contentContainerStyle={styles.previewRow}>
            {assets.map((asset) => (
              <Image
                key={asset.uri}
                source={{ uri: asset.uri }}
                style={styles.preview}
              />
            ))}
          </ScrollView>
        ) : (
          <View style={styles.placeholder}>
            <Text style={styles.placeholderText}>
              No photos selected yet. Add a few shots to create a draft.
            </Text>
          </View>
        )}
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
        {pending && <ActivityIndicator style={{ marginBottom: 12 }} />}
        {error && <Text style={styles.error}>{error}</Text>}
        {status && <Text style={styles.status}>{status}</Text>}
        <View style={styles.buttonRow}>
          <Button
            title={pending ? "Uploading..." : "Upload"}
            onPress={onUpload}
            disabled={pending || files.length === 0}
          />
          <Button
            title="Clear"
            onPress={clearForm}
            disabled={!assets.length && !brand && !size}
          />
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
  safe: {
    flex: 1,
    backgroundColor: "#fff",
  },
  container: {
    padding: 20,
    gap: 16,
  },
  heading: {
    fontSize: 24,
    fontWeight: "700",
  },
  description: {
    color: "#6b7280",
  },
  code: {
    fontWeight: "700",
  },
  buttonRow: {
    flexDirection: "row",
    gap: 12,
    flexWrap: "wrap",
  },
  previewRow: {
    gap: 12,
  },
  preview: {
    width: 120,
    height: 160,
    borderRadius: 12,
  },
  placeholder: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    padding: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderText: {
    color: "#6b7280",
    textAlign: "center",
  },
  field: {
    gap: 8,
  },
  label: {
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  helper: {
    color: "#6b7280",
  },
  status: {
    color: "#065f46",
    backgroundColor: "#d1fae5",
    padding: 10,
    borderRadius: 8,
  },
  error: {
    color: "#991b1b",
    backgroundColor: "#fef2f2",
    padding: 10,
    borderRadius: 8,
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  chipActive: {
    backgroundColor: "#111827",
    borderColor: "#111827",
  },
  chipText: {
    color: "#374151",
    fontWeight: "600",
  },
  chipTextActive: {
    color: "#fff",
  },
});
