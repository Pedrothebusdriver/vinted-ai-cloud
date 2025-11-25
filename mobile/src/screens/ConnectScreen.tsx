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
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { fetchHealth } from "../api";
import { Config } from "../config";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Connect">;

export const ConnectScreen = ({ navigation }: Props) => {
  const {
    baseUrl,
    uploadKey,
    lastConnected,
    servers,
    setBaseUrl,
    setUploadKey,
    setLastConnected,
    addServer,
    selectServer,
    hydrated,
  } = useServer();
  const insets = useSafeAreaInsets();
  const [url, setUrl] = useState(baseUrl);
  const [key, setKey] = useState(uploadKey || "");
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [serverVersion, setServerVersion] = useState<string | null>(null);

  const resolvedBase = useMemo(
    () => cleanUrl || baseUrl || Config.apiBase,
    [baseUrl, cleanUrl]
  );

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
    setServerVersion(null);
    try {
      const data = await fetchHealth(resolvedBase, {
        uploadKey: cleanKey || null,
      });
      const text = data.version
        ? `Server ready (version ${data.version})`
        : "Server responded.";
      setStatus("ok");
      setMessage(text);
      setServerVersion(data.version || null);
      setBaseUrl(resolvedBase);
      setUploadKey(cleanKey || null);
      setLastConnected(new Date().toISOString());
    } catch (err: any) {
      setStatus("error");
      setMessage(formatConnectionError(err, resolvedBase));
      setServerVersion(null);
    } finally {
      setPending(false);
    }
  }, [cleanKey, resolvedBase, setBaseUrl, setLastConnected, setUploadKey]);

  const proceed = useCallback(() => {
    setBaseUrl(resolvedBase);
    setUploadKey(cleanKey || null);
    navigation.navigate("Drafts");
  }, [cleanKey, navigation, resolvedBase, setBaseUrl, setUploadKey]);

  const onRefresh = useCallback(async () => {
    if (pending) return;
    setRefreshing(true);
    try {
      await testConnection();
    } finally {
      setRefreshing(false);
    }
  }, [pending, testConnection]);

  const onSaveServer = useCallback(() => {
    const targetUrl = resolvedBase;
    if (!targetUrl) return;
    addServer({
      baseUrl: targetUrl,
      uploadKey: cleanKey || uploadKey || null,
      lastConnected,
    });
  }, [addServer, cleanKey, lastConnected, resolvedBase, uploadKey]);

  const versionMismatch =
    !!serverVersion && serverVersion !== Config.coreSchemaVersion;

  const footerInset = Math.max(insets.bottom, 12);
  const contentPaddingBottom = footerInset + 120;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.body}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={[
            styles.container,
            { paddingBottom: contentPaddingBottom },
          ]}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
        >
          <Text style={styles.heading}>FlipLens server</Text>
          <Text style={styles.description}>
            Enter the Pi or Core server URL. We&apos;ll remember this for
            uploads and drafts.
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
              style={[
                styles.status,
                status === "ok" ? styles.ok : styles.error,
              ]}
            >
              {message}
            </Text>
          )}
          {serverVersion && (
            <Text
              style={[
                styles.version,
                versionMismatch && styles.versionWarning,
              ]}
            >
              Server version: {serverVersion} · Expected:{" "}
              {Config.coreSchemaVersion}
            </Text>
          )}
          <Button
            title="Save this server"
            onPress={onSaveServer}
            disabled={!cleanUrl && !baseUrl}
          />
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
          {servers.length > 0 && (
            <View style={styles.savedList}>
              <Text style={styles.savedHeading}>Saved servers</Text>
              {servers.map((server) => {
                let label = server.label || server.baseUrl;
                let savedLast: string | null = null;
                if (server.lastConnected) {
                  try {
                    savedLast = new Date(server.lastConnected).toLocaleString();
                  } catch {
                    savedLast = server.lastConnected;
                  }
                }
                const isActive =
                  server.baseUrl === baseUrl &&
                  (server.uploadKey || null) === (uploadKey || null);
                return (
                  <TouchableOpacity
                    key={server.id}
                    style={[
                      styles.savedCard,
                      isActive && styles.savedCardActive,
                    ]}
                    onPress={() => selectServer(server.id)}
                  >
                    <Text style={styles.savedLabel}>{label}</Text>
                    <Text style={styles.savedUrl}>{server.baseUrl}</Text>
                    {savedLast && (
                      <Text style={styles.savedMeta}>
                        Last connected: {savedLast}
                      </Text>
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </ScrollView>
        <View
          style={[
            styles.footer,
            {
              paddingBottom: footerInset,
            },
          ]}
        >
          <Button
            title="Continue"
            onPress={proceed}
            disabled={!hydrated || pending || !resolvedBase}
          />
        </View>
      </View>
    </SafeAreaView>
  );
};

const formatConnectionError = (err: any, url: string | undefined) => {
  if (!url) return "Missing server URL. Enter the Pi address first.";
  const baseMessage = err?.message || "Unable to reach server.";
  return `${baseMessage} · Check Wi‑Fi and confirm ${url} is reachable on the same network.`;
};

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#fff",
  },
  body: {
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
  version: {
    color: "#2563eb",
    fontWeight: "600",
  },
  versionWarning: {
    color: "#b91c1c",
  },
  savedList: {
    gap: 12,
    paddingVertical: 12,
  },
  savedHeading: {
    fontSize: 16,
    fontWeight: "600",
  },
  savedCard: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 10,
    padding: 12,
    gap: 4,
  },
  savedCardActive: {
    borderColor: "#2563eb",
    backgroundColor: "#eff6ff",
  },
  savedLabel: {
    fontWeight: "600",
  },
  savedUrl: {
    color: "#4b5563",
    fontSize: 13,
  },
  savedMeta: {
    color: "#6b7280",
    fontSize: 12,
  },
  code: {
    fontFamily: Platform.select({
      ios: "Menlo",
      default: "monospace",
    }),
    fontWeight: "600",
  },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 24,
    paddingTop: 12,
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderColor: "#e5e7eb",
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: -2 },
  },
});
