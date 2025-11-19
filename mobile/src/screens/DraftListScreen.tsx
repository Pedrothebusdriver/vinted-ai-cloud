import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Button,
  FlatList,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { DraftStatus, DraftSummary, fetchDrafts } from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";
import { ServerSettingsModal } from "../components/ServerSettingsModal";

type Props = NativeStackScreenProps<RootStackParamList, "Drafts">;
type FilterValue = "all" | DraftStatus;

const PLACEHOLDER_DRAFTS: DraftSummary[] = [
  {
    id: 101,
    title: "Sample Nike Tech Fleece",
    brand: "Nike",
    size: "M",
    colour: "Charcoal",
    price_mid: 55,
    status: "draft",
  },
  {
    id: 102,
    title: "Vintage Levi's 501s",
    brand: "Levi's",
    size: "W32 L32",
    colour: "Stonewash",
    price_mid: 35,
    status: "ready",
  },
];

const FILTERS: { label: string; value: FilterValue }[] = [
  { label: "All", value: "all" },
  { label: "Drafts", value: "draft" },
  { label: "Ready", value: "ready" },
];

export const DraftListScreen = ({ navigation }: Props) => {
  const { baseUrl, uploadKey } = useServer();
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterValue>("all");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const loadDrafts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters = filter === "all" ? undefined : { status: filter };
      const data = await fetchDrafts(baseUrl, {
        filters,
        uploadKey,
      });
      setDrafts(data);
    } catch (err: any) {
      setError(err.message || "Unable to load drafts, showing samples.");
      setDrafts(
        filter === "all"
          ? PLACEHOLDER_DRAFTS
          : PLACEHOLDER_DRAFTS.filter((draft) => draft.status === filter)
      );
    } finally {
      setLoading(false);
    }
  }, [baseUrl, filter, uploadKey]);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  const renderItem = ({ item }: { item: DraftSummary }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => navigation.navigate("DraftDetail", { id: item.id })}
    >
      <View style={styles.thumbnailWrapper}>
        {item.thumbnail_url ? (
          <Image
            source={{ uri: item.thumbnail_url }}
            style={styles.thumbnail}
          />
        ) : (
          <View style={styles.thumbnailPlaceholder}>
            <Text style={styles.thumbnailPlaceholderText}>
              {item.photo_count
                ? `${item.photo_count} photo${
                    item.photo_count > 1 ? "s" : ""
                  }`
                : "Photos"}
            </Text>
          </View>
        )}
      </View>
      <View style={styles.cardBody}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>{item.title}</Text>
          <StatusChip status={item.status} />
        </View>
        <Text style={styles.meta}>
          {item.brand || "Unknown brand"} · {item.size || "Size ?"}
        </Text>
        <Text style={styles.meta}>{item.colour || "Colour ?"}</Text>
        <Text style={styles.price}>
          {item.price_mid ? `£${item.price_mid}` : "Price TBD"}
        </Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.heading}>Drafts</Text>
        <View style={styles.headerActions}>
          <Button title="Settings" onPress={() => setSettingsOpen(true)} />
          <Button
            title="Upload photos"
            onPress={() => navigation.navigate("Upload")}
          />
        </View>
      </View>
      <Text style={styles.server}>Server: {baseUrl}</Text>
      <View style={styles.filterRow}>
        {FILTERS.map((option) => (
          <TouchableOpacity
            key={option.value}
            style={[
              styles.filterChip,
              filter === option.value && styles.filterChipActive,
            ]}
            onPress={() => setFilter(option.value)}
          >
            <Text
              style={[
                styles.filterText,
                filter === option.value && styles.filterTextActive,
              ]}
            >
              {option.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
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
      <ServerSettingsModal
        visible={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </SafeAreaView>
  );
};

const StatusChip = ({ status }: { status?: string }) => {
  if (!status) return null;
  const label =
    status === "ready"
      ? "Ready"
      : status === "draft"
      ? "Draft"
      : status.charAt(0).toUpperCase() + status.slice(1);
  return (
    <View
      style={[
        styles.statusChip,
        status === "ready" ? styles.statusReady : styles.statusDraft,
      ]}
    >
      <Text
        style={[
          styles.statusChipText,
          status === "ready"
            ? styles.statusReadyText
            : styles.statusDraftText,
        ]}
      >
        {label}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#fff",
  },
  header: {
    padding: 20,
    gap: 12,
  },
  heading: {
    fontSize: 24,
    fontWeight: "700",
  },
  headerActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 12,
  },
  server: {
    paddingHorizontal: 20,
    color: "#6b7280",
  },
  filterRow: {
    flexDirection: "row",
    paddingHorizontal: 20,
    gap: 8,
    marginTop: 12,
  },
  filterChip: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  filterChipActive: {
    backgroundColor: "#111827",
    borderColor: "#111827",
  },
  filterText: {
    color: "#374151",
    fontWeight: "600",
  },
  filterTextActive: {
    color: "#fff",
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
    flexDirection: "row",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    overflow: "hidden",
    minHeight: 140,
  },
  thumbnailWrapper: {
    width: 112,
    backgroundColor: "#f3f4f6",
  },
  thumbnail: {
    width: "100%",
    height: "100%",
  },
  thumbnailPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    padding: 12,
  },
  thumbnailPlaceholderText: {
    color: "#6b7280",
    textAlign: "center",
  },
  cardBody: {
    flex: 1,
    padding: 16,
    gap: 4,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
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
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  statusDraft: {
    backgroundColor: "#fef3c7",
  },
  statusDraftText: {
    color: "#92400e",
  },
  statusReady: {
    backgroundColor: "#dcfce7",
  },
  statusReadyText: {
    color: "#166534",
  },
  statusChipText: {
    fontWeight: "600",
    fontSize: 12,
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
