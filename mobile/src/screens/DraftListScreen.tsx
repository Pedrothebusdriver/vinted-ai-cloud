import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Button,
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { DraftSummary, fetchDrafts } from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Drafts">;

const PLACEHOLDER_DRAFTS: DraftSummary[] = [
  {
    id: 101,
    title: "Sample Nike Tech Fleece",
    brand: "Nike",
    size: "M",
    colour: "Charcoal",
    price_mid: 55,
  },
  {
    id: 102,
    title: "Vintage Levi's 501s",
    brand: "Levi's",
    size: "W32 L32",
    colour: "Stonewash",
    price_mid: 35,
  },
];

export const DraftListScreen = ({ navigation }: Props) => {
  const { baseUrl } = useServer();
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDrafts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDrafts(baseUrl);
      setDrafts(data);
    } catch (err: any) {
      setError(err.message || "Unable to load drafts, showing samples.");
      setDrafts(PLACEHOLDER_DRAFTS);
    } finally {
      setLoading(false);
    }
  }, [baseUrl]);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  const renderItem = ({ item }: { item: DraftSummary }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => navigation.navigate("DraftDetail", { id: item.id })}
    >
      <Text style={styles.cardTitle}>{item.title}</Text>
      <Text style={styles.meta}>
        {item.brand || "Unknown brand"} · {item.size || "Size ?"}
      </Text>
      <Text style={styles.meta}>{item.colour || "Colour ?"}</Text>
      <Text style={styles.price}>
        {item.price_mid ? `£${item.price_mid}` : "Price TBD"}
      </Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.heading}>Drafts</Text>
        <Button
          title="Upload photos"
          onPress={() => navigation.navigate("Upload")}
        />
      </View>
      <Text style={styles.server}>Server: {baseUrl}</Text>
      {loading && <ActivityIndicator style={{ marginVertical: 12 }} />}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <FlatList
        data={drafts}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshing={loading}
        onRefresh={loadDrafts}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>
                No drafts yet. Tap &quot;Upload photos&quot; to start.
              </Text>
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#fff",
  },
  header: {
    padding: 20,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  heading: {
    fontSize: 24,
    fontWeight: "700",
  },
  server: {
    paddingHorizontal: 20,
    color: "#6b7280",
  },
  error: {
    margin: 20,
    backgroundColor: "#fef2f2",
    color: "#991b1b",
    padding: 12,
    borderRadius: 8,
  },
  list: {
    padding: 20,
    gap: 12,
  },
  card: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    padding: 16,
    borderRadius: 12,
    gap: 4,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "600",
  },
  meta: {
    color: "#4b5563",
  },
  price: {
    marginTop: 8,
    fontWeight: "700",
    color: "#111827",
  },
  empty: {
    padding: 40,
    alignItems: "center",
  },
  emptyText: {
    color: "#6b7280",
    textAlign: "center",
  },
});
