import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Modal,
  StyleSheet,
  Text,
  TextInput,
  TouchableWithoutFeedback,
  View,
} from "react-native";
import { useServer } from "../state/ServerContext";

type Props = {
  visible: boolean;
  onClose: () => void;
};

const isValidUrl = (value: string) => /^https?:\/\//i.test(value);

export const ServerSettingsModal = ({ visible, onClose }: Props) => {
  const { baseUrl, uploadKey, setBaseUrl, setUploadKey } = useServer();
  const [url, setUrl] = useState(baseUrl);
  const [key, setKey] = useState(uploadKey || "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      setUrl(baseUrl);
      setKey(uploadKey || "");
      setError(null);
    }
  }, [baseUrl, uploadKey, visible]);

  const cleanUrl = useMemo(() => url.trim(), [url]);
  const cleanKey = useMemo(() => key.trim(), [key]);

  const onSave = () => {
    if (!cleanUrl) {
      setError("Server URL is required.");
      return;
    }
    if (!isValidUrl(cleanUrl)) {
      setError("Enter a valid http:// or https:// URL.");
      return;
    }
    setError(null);
    setBaseUrl(cleanUrl);
    setUploadKey(cleanKey || null);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <TouchableWithoutFeedback onPress={onClose}>
        <View style={styles.backdrop} />
      </TouchableWithoutFeedback>
      <View style={styles.center}>
        <View style={styles.card}>
          <Text style={styles.title}>App Settings</Text>
          <Text style={styles.description}>
            Update the server URL or upload key at any time. These values are
            shared across all screens.
          </Text>
          <View style={styles.field}>
            <Text style={styles.label}>Server URL</Text>
            <TextInput
              style={styles.input}
              value={url}
              onChangeText={setUrl}
              autoCapitalize="none"
              placeholder="http://192.168.0.21:10000"
            />
          </View>
          <View style={styles.field}>
            <Text style={styles.label}>Upload key</Text>
            <TextInput
              style={styles.input}
              value={key}
              onChangeText={setKey}
              autoCapitalize="none"
              placeholder="Optional secret"
            />
          </View>
          {error && <Text style={styles.error}>{error}</Text>}
          <View style={styles.actions}>
            <Button title="Cancel" onPress={onClose} />
            <Button title="Save" onPress={onSave} />
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  center: {
    flex: 1,
    justifyContent: "center",
    padding: 24,
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    gap: 16,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  description: {
    color: "#6b7280",
  },
  field: {
    gap: 6,
  },
  label: {
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    padding: 12,
  },
  error: {
    color: "#b91c1c",
    backgroundColor: "#fee2e2",
    borderRadius: 8,
    padding: 10,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
  },
});
