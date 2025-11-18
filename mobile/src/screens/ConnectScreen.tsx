import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Button,
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
  const { baseUrl, setBaseUrl, hydrated } = useServer();
  const [url, setUrl] = useState(baseUrl);
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (hydrated) {
      setUrl(baseUrl);
    }
  }, [baseUrl, hydrated]);

  const cleanUrl = useMemo(() => url.trim(), [url]);

  const testConnection = useCallback(async () => {
    setPending(true);
    setStatus("idle");
    setMessage(null);
    try {
      const data = await fetchHealth(cleanUrl || baseUrl);
      const text = data.version
        ? `Server ready (version ${data.version})`
        : "Server responded.";
      setStatus("ok");
      setMessage(text);
      setBaseUrl(cleanUrl || baseUrl);
    } catch (err: any) {
      setStatus("error");
      setMessage(err.message || "Unable to reach server.");
    } finally {
      setPending(false);
    }
  }, [baseUrl, cleanUrl, setBaseUrl]);

  const proceed = useCallback(() => {
    setBaseUrl(cleanUrl || baseUrl);
    navigation.navigate("Drafts");
  }, [baseUrl, cleanUrl, navigation, setBaseUrl]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
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
        <View style={styles.divider} />
        <Button
          title="Continue"
          onPress={proceed}
          disabled={!hydrated || pending}
        />
      </View>
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
});
