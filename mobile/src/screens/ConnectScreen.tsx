import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
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
import { Config } from "../config";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";
import { colors, radius, shadows, spacing } from "../theme/tokens";
import { ui } from "../theme/components";

type Props = NativeStackScreenProps<RootStackParamList, "Connect">;

export const normalizeBaseUrl = (raw: string): string => {
  const trimmed = (raw || "").trim();
  if (!trimmed) {
    throw new Error("Missing server URL");
  }
  const withProto = trimmed.startsWith("http") ? trimmed : `http://${trimmed}`;
  return withProto.replace(/\/$/, "");
};

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

  const cleanUrl = useMemo(() => (url || "").trim(), [url]);
  const cleanKey = useMemo(() => key.trim(), [key]);
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

    const candidate = cleanUrl || baseUrl || Config.apiBase;

    let normalized: string;
    try {
      normalized = normalizeBaseUrl(candidate);
    } catch (err: any) {
      setPending(false);
      setStatus("error");
      setMessage(err?.message || "Missing or invalid server URL");
      return;
    }

    const testedUrl = `${normalized}/health`;
    console.log("[FlipLens] TestConnection: testing", testedUrl);

    try {
      const res = await fetch(testedUrl);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json().catch(() => ({} as any));
      const text = data.version
        ? `Server ready (version ${data.version})`
        : "Server responded.";

      const timestamp = new Date().toISOString();

      setStatus("ok");
      setMessage(`${text} · ${testedUrl}`);
      setServerVersion(data?.version || null);

      setBaseUrl(normalized);
      setUploadKey(cleanKey || null);
      setLastConnected(timestamp);
      addServer({
        baseUrl: normalized,
        uploadKey: cleanKey || null,
        lastConnected: timestamp,
      });
    } catch (err: any) {
      console.log("[FlipLens] TestConnection error for", testedUrl, err);
      setStatus("error");
      setMessage(
        `Network request timed out or failed.\nTested: ${testedUrl}\nError: ${
          err?.message || String(err)
        }`
      );
      setServerVersion(null);
    } finally {
      setPending(false);
    }
  }, [
    addServer,
    baseUrl,
    cleanKey,
    setBaseUrl,
    setLastConnected,
    setUploadKey,
    cleanUrl,
  ]);

  const proceed = useCallback(() => {
    try {
      const normalized = normalizeBaseUrl(cleanUrl || baseUrl || Config.apiBase);
      setBaseUrl(normalized);
      setUploadKey(cleanKey || null);
      navigation.navigate("Drafts");
    } catch (err) {
      setStatus("error");
      setMessage(
        (err as Error)?.message || "Missing or invalid server URL to continue"
      );
    }
  }, [
    baseUrl,
    cleanKey,
    cleanUrl,
    navigation,
    setBaseUrl,
    setUploadKey,
  ]);

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
    <SafeAreaView style={ui.screen}>
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
          <Text style={ui.headingXL}>FlipLens server</Text>
          <Text style={ui.subheading}>
            Enter the Pi or Core server URL. We&apos;ll remember this for uploads and drafts.
          </Text>
          <View style={styles.infoRow}>
            <View style={[ui.card, styles.infoCard]}>
              <Text style={styles.cardLabel}>Current backend</Text>
              <Text style={styles.cardValue}>{resolvedBase || "Not connected"}</Text>
              {lastConnectedLabel && (
                <Text style={styles.cardMeta}>Last check: {lastConnectedLabel}</Text>
              )}
            </View>
            <View style={[ui.mutedCard, styles.quickCard]}>
              <Text style={styles.cardLabel}>Upload key</Text>
              <TextInput
                style={styles.input}
                value={key}
                onChangeText={setKey}
                autoCapitalize="none"
                autoCorrect={false}
                placeholder="upload-secret"
              />
              <Text style={styles.helper}>
                Sent as <Text style={styles.code}>X-Upload-Key</Text> on every request.
              </Text>
            </View>
          </View>
          <View style={[ui.card, styles.inlineCard]}>
            <Text style={ui.label}>Server URL</Text>
            <TextInput
              style={styles.input}
              value={url}
              onChangeText={setUrl}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="http://192.168.0.21:10000"
            />
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={[ui.primaryButton, pending && styles.disabled]}
                onPress={testConnection}
                disabled={pending}
                activeOpacity={0.9}
              >
                <Text style={ui.primaryButtonText}>
                  {pending ? "Testing connection..." : "Test Connection"}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={ui.secondaryButton}
                onPress={onSaveServer}
                disabled={!cleanUrl && !baseUrl}
                activeOpacity={0.9}
              >
                <Text style={ui.secondaryButtonText}>Save</Text>
              </TouchableOpacity>
            </View>
            {pending && <ActivityIndicator style={{ marginTop: 12 }} />}
            {status !== "idle" && (
              <View
                style={[
                  styles.statusCard,
                  status === "ok" ? styles.statusOk : styles.statusError,
                ]}
              >
                <Text style={styles.statusText}>{message}</Text>
                {serverVersion && (
                  <Text
                    style={[
                      styles.version,
                      versionMismatch && styles.versionWarning,
                    ]}
                  >
                    Server version: {serverVersion} · Expected: {Config.coreSchemaVersion}
                  </Text>
                )}
              </View>
            )}
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
                    onPress={() => {
                      setUrl(server.baseUrl);
                      setKey(server.uploadKey || "");
                      selectServer(server.id);
                    }}
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
          <TouchableOpacity
            style={[
              ui.primaryButton,
              styles.footerButton,
              (!hydrated || pending || !resolvedBase) && styles.disabled,
            ]}
            onPress={proceed}
            disabled={!hydrated || pending || !resolvedBase}
            activeOpacity={0.9}
          >
            <Text style={ui.primaryButtonText}>Continue</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  body: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    flex: 1,
    padding: spacing.xl,
    gap: spacing.lg,
  },
  input: {
    ...ui.input,
    backgroundColor: colors.card,
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  disabled: {
    opacity: 0.65,
  },
  statusCard: {
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    gap: spacing.xs,
  },
  statusOk: {
    backgroundColor: "#ecfdf5",
    borderColor: "#bbf7d0",
  },
  statusError: {
    backgroundColor: "#fef2f2",
    borderColor: "#fecdd3",
  },
  statusText: {
    color: colors.text,
  },
  divider: {
    borderBottomWidth: 1,
    borderColor: colors.border,
    marginVertical: spacing.md,
  },
  field: {
    gap: spacing.xs,
  },
  label: {
    fontSize: 16,
    fontWeight: "600",
    color: colors.text,
  },
  helper: {
    color: colors.muted,
  },
  meta: {
    ...ui.meta,
  },
  version: {
    color: colors.accent,
    fontWeight: "600",
  },
  versionWarning: {
    color: colors.danger,
  },
  infoCard: {
    flex: 1,
    gap: spacing.xs,
  },
  quickCard: {
    flex: 1,
    gap: spacing.sm,
  },
  infoRow: {
    flexDirection: "row",
    gap: spacing.md,
    flexWrap: "wrap",
  },
  inlineCard: {
    gap: spacing.sm,
  },
  cardLabel: {
    ...ui.helper,
    fontWeight: "700",
  },
  cardValue: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.text,
    marginTop: spacing.xs,
  },
  cardMeta: {
    color: colors.muted,
    marginTop: spacing.xs,
  },
  savedList: {
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  savedHeading: {
    ...ui.label,
  },
  savedCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
    backgroundColor: colors.card,
  },
  savedCardActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  savedLabel: {
    fontWeight: "600",
    color: colors.text,
  },
  savedUrl: {
    color: colors.muted,
    fontSize: 13,
  },
  savedMeta: {
    color: colors.muted,
    fontSize: 12,
  },
  code: {
    fontFamily: Platform.select({
      ios: "Menlo",
      default: "monospace",
    }),
    fontWeight: "600",
    color: colors.text,
  },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    backgroundColor: colors.card,
    borderTopWidth: 1,
    borderColor: colors.border,
    ...shadows.card,
  },
  footerButton: {
    flex: 1,
  },
});
