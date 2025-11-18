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
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import { uploadImages, UploadFileInput } from "../api";
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
  const [metadata, setMetadata] = useState("");
  const [pending, setPending] = useState(false);
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

  const clearSelection = useCallback(() => {
    setAssets([]);
    setStatus(null);
  }, []);

  const onUpload = useCallback(async () => {
    if (!files.length) {
      Alert.alert("Add photos", "Select at least one photo to upload.");
      return;
    }
    setPending(true);
    setStatus(null);
    try {
      const response = await uploadImages(
        baseUrl,
        files,
        metadata.trim() || undefined,
        { uploadKey }
      );
      const newId = response?.item_id;
      setStatus("Upload complete. Opening draft...");
      if (newId) {
        navigation.navigate("DraftDetail", { id: newId });
        clearSelection();
      } else {
        Alert.alert(
          "Uploaded",
          "Photos uploaded. Refresh the Drafts list to see the new item."
        );
      }
    } catch (err: any) {
      Alert.alert("Upload failed", err?.message || "Unable to upload photos.");
    } finally {
      setPending(false);
    }
  }, [baseUrl, clearSelection, files, metadata, navigation, uploadKey]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.heading}>Upload photos</Text>
        <Text style={styles.description}>
          We send selected photos to <Text style={styles.code}>/api/upload</Text>{" "}
          for now. Once <Text style={styles.code}>POST /api/drafts</Text> ships,
          this screen will reuse the same payload builder.
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
          <Text style={styles.label}>Metadata (JSON)</Text>
          <TextInput
            style={[styles.input, styles.multiline]}
            multiline
            numberOfLines={4}
            value={metadata}
            onChangeText={setMetadata}
            placeholder='{"brand":"Nike","size":"M"}'
          />
          <Text style={styles.helper}>
            Temporary helper until we wire simple inputs; the backend expects
            JSON with brand/size/condition for now.
          </Text>
        </View>
        {pending && <ActivityIndicator style={{ marginBottom: 12 }} />}
        {status && <Text style={styles.status}>{status}</Text>}
        <View style={styles.buttonRow}>
          <Button
            title={pending ? "Uploading..." : "Upload"}
            onPress={onUpload}
            disabled={pending || files.length === 0}
          />
          <Button title="Clear" onPress={clearSelection} disabled={!assets.length} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

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
  multiline: {
    minHeight: 100,
    textAlignVertical: "top",
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
});
