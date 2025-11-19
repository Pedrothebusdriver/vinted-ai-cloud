import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Button,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { fetchHealth } from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Connect">;

export const ConnectScreen = ({ navigation }: Props) => {
  const {
    baseUrl,
    uploadKey,
    lastConnected,
    setBaseUrl,
    setUploadKey,
    setLastConnected,
    hydrated,
  } = useServer();
  const [url, setUrl] = useState(baseUrl);
  const [key, setKey] = useState(uploadKey || "");
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (hydrated) {
      setUrl(baseUrl);
      setKey(uploadKey || "");
    }
  }, [baseUrl, hydrated, uploadKey]);

  const cleanUrl = useMemo(() => url.trim(), [url]);
  const cleanKey = useMemo(() => key.trim(), [key]);

  const lastConnectedLabel = useMemo(() => {
    if (!lastConnected) return null;
    try {
      return new Date(lastConnected).toLocaleString();
    } catch {
      return lastConnected;
    }
  }, [lastConnected]);

  const testConnection = useCallback(async () => {
    setPending(true);
    setStatus("idle");
    setMessage(null);
    try {
      const data = await fetchHealth(cleanUrl || baseUrl, {
        uploadKey: cleanKey || null,
      });
      const text = data.version
        ? `Server ready (version ${data.version})`
        : "Server responded.";
      setStatus("ok");
      setMessage(text);
      setBaseUrl(cleanUrl || baseUrl);
      setUploadKey(cleanKey || null);
      setLastConnected(new Date().toISOString());
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message || "Unable to reach server.");
    } finally {
      setPending(false);
    }
  }, [baseUrl, cleanKey, cleanUrl, setBaseUrl, setLastConnected, setUploadKey]);

  const proceed = useCallback(() => {
    setBaseUrl(cleanUrl || baseUrl);
    setUploadKey(cleanKey || null);
    navigation.navigate("Drafts");
  }, [baseUrl, cleanKey, cleanUrl, navigation, setBaseUrl, setUploadKey]);

  const onRefresh = useCallback(async () => {
    if (pending) return;
    setRefreshing(true);
    try {
      await testConnection();
    } finally {
      setRefreshing(false);
    }
  }, [pending, testConnection]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        <Text style={styles.heading}>FlipLens server</Text>
        <Text style={styles.description}>
          Enter the Pi or Core server URL. We&apos;ll remember this for uploads
          and drafts.
        </Text>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={setUrl}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="http://192.168.0.10:8080"
        />
        <Button
          title={pending ? "Checking..." : "Test Connection"}
          onPress={testConnection}
          disabled={pending}
        />
        {pending && <ActivityIndicator style={{ marginTop: 12 }} />}
        {status !== "idle" && (
          <Text
            style={[styles.status, status === "ok" ? styles.ok : styles.error]}
          >
            {message}
          </Text>
        )}
        <View style={styles.field}>
          <Text style={styles.label}>Upload key (optional)</Text>
          <TextInput
            style={styles.input}
            value={key}
            onChangeText={setKey}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder="upload-secret"
          />
          <Text style={styles.helper}>
            We send this as <Text style={styles.code}>X-Upload-Key</Text> on
            every request once the server enforces auth.
          </Text>
        </View>
        <View style={styles.divider} />
        {lastConnectedLabel && (
          <Text style={styles.meta}>
            Last connected: {lastConnectedLabel}
          </Text>
        )}
        <Button
          title="Continue"
          onPress={proceed}
          disabled={!hydrated || pending}
        />
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
    flex: 1,
    padding: 24,
    gap: 16,
  },
  heading: {
    fontSize: 28,
    fontWeight: "700",
  },
  description: {
    color: "#4b5563",
  },
  input: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    padding: 14,
    fontSize: 16,
  },
  status: {
    padding: 12,
    borderRadius: 8,
  },
  ok: {
    backgroundColor: "#ecfdf5",
    color: "#047857",
  },
  error: {
    backgroundColor: "#fef2f2",
    color: "#b91c1c",
  },
  divider: {
    borderBottomWidth: 1,
    borderColor: "#f3f4f6",
    marginVertical: 12,
  },
  field: {
    gap: 8,
  },
  label: {
    fontSize: 16,
    fontWeight: "600",
  },
  helper: {
    color: "#6b7280",
  },
  meta: {
    color: "#4b5563",
  },
  code: {
    fontFamily: Platform.select({
      ios: "Menlo",
      default: "monospace",
    }),
    fontWeight: "600",
  },
});
