import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Button,
  FlatList,
  Image,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import {
  DraftListFilters,
  DraftStatus,
  DraftSummary,
  fetchDrafts,
} from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";
import { ServerSettingsModal } from "../components/ServerSettingsModal";
import { DraftFilterSheet } from "../components/DraftFilterSheet";

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

const PAGE_SIZE = 20;
const SKELETON_ITEMS = new Array(3).fill(null);

export const DraftListScreen = ({ navigation }: Props) => {
  const { baseUrl, uploadKey } = useServer();
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterValue>("all");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState<{
    brand?: string;
    size?: string;
  }>({});
  const draftsRef = useRef<DraftSummary[]>([]);
  const hasMoreRef = useRef(true);
  const filtersKey = `${filter}-${advancedFilters.brand ?? ""}-${advancedFilters.size ?? ""}`;
  const hasAdvancedFilters = Boolean(
    advancedFilters.brand || advancedFilters.size
  );

  const loadDrafts = useCallback(
    async ({ append = false }: { append?: boolean } = {}) => {
      if (append && !hasMoreRef.current) {
        return;
      }
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setError(null);
      }
      try {
        const filtersPayload: DraftListFilters = {
          ...advancedFilters,
        };
        if (filter !== "all") {
          filtersPayload.status = filter;
        }
        const offset = append ? draftsRef.current.length : 0;
        const data = await fetchDrafts(baseUrl, {
          filters: filtersPayload,
          uploadKey,
          pagination: {
            limit: PAGE_SIZE,
            offset,
          },
        });
        setDrafts((prev) => (append ? [...prev, ...data] : data));
        setHasMore(data.length === PAGE_SIZE);
      } catch (err: any) {
        const fallbackMessage = err.message || "Unable to load drafts.";
        setError(
          append
            ? `${fallbackMessage} Pull to refresh to try again.`
            : `${fallbackMessage} Showing samples.`
        );
        if (!append) {
          const fallbackDrafts = (filter === "all"
            ? PLACEHOLDER_DRAFTS
            : PLACEHOLDER_DRAFTS.filter((draft) => draft.status === filter)
          ).filter((draft) => {
            if (advancedFilters.brand) {
              if (
                !draft.brand ||
                !draft.brand
                  .toLowerCase()
                  .includes(advancedFilters.brand.toLowerCase())
              ) {
                return false;
              }
            }
            if (advancedFilters.size) {
              if (
                !draft.size ||
                !draft.size
                  .toLowerCase()
                  .includes(advancedFilters.size.toLowerCase())
              ) {
                return false;
              }
            }
            return true;
          });
          setDrafts(fallbackDrafts);
          setHasMore(false);
        }
      } finally {
        if (append) {
          setLoadingMore(false);
        } else {
          setLoading(false);
        }
      }
    },
    [advancedFilters, baseUrl, filter, uploadKey]
  );


  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);

  useEffect(() => {
    hasMoreRef.current = hasMore;
  }, [hasMore]);

  useEffect(() => {
    setHasMore(true);
    hasMoreRef.current = true;
    loadDrafts();
  }, [filtersKey, loadDrafts]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadDrafts({ append: false });
    } finally {
      setRefreshing(false);
    }
  }, [loadDrafts]);

  const onEndReached = useCallback(() => {
    if (loading || loadingMore) return;
    loadDrafts({ append: true });
  }, [loadDrafts, loading, loadingMore]);

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
        <TouchableOpacity
          style={[
            styles.filterButton,
            hasAdvancedFilters && styles.filterButtonActive,
          ]}
          onPress={() => setFiltersOpen(true)}
        >
          <Text
            style={[
              styles.filterButtonText,
              hasAdvancedFilters && styles.filterButtonTextActive,
            ]}
          >
            Filters
          </Text>
        </TouchableOpacity>
      </View>
      {hasAdvancedFilters && (
        <Text style={styles.filterSummary}>
          Active filters:
          {advancedFilters.brand ? ` Brand=${advancedFilters.brand}` : ""}
          {advancedFilters.size ? ` Size=${advancedFilters.size}` : ""}
        </Text>
      )}
      {loading && <ActivityIndicator style={{ marginVertical: 12 }} />}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <FlatList
        data={drafts}
        keyExtractor={(item) => String(item.id)}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        onEndReached={onEndReached}
        onEndReachedThreshold={0.4}
        ListFooterComponent={
          loadingMore || !hasMore ? (
            <View style={styles.footer}>
              {loadingMore ? (
                <ActivityIndicator />
              ) : (
                <Text style={styles.footerText}>No more drafts.</Text>
              )}
            </View>
          ) : null
        }
        ListEmptyComponent={
          loading ? (
            <View style={styles.skeletonContainer}>
              {SKELETON_ITEMS.map((_, idx) => (
                <SkeletonCard key={idx} />
              ))}
            </View>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>
                No drafts yet. Tap &quot;Upload photos&quot; to start.
              </Text>
            </View>
          )
        }
      />
      <ServerSettingsModal
        visible={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
      <DraftFilterSheet
        visible={filtersOpen}
        status={filter}
        statusOptions={FILTERS}
        onStatusChange={(value) => setFilter(value as FilterValue)}
        brand={advancedFilters.brand}
        size={advancedFilters.size}
        onApply={(filters) => setAdvancedFilters(filters)}
        onClear={() => setAdvancedFilters({})}
        onClose={() => setFiltersOpen(false)}
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

const SkeletonCard = () => {
  const shimmer = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(shimmer, {
          toValue: 1,
          duration: 900,
          useNativeDriver: true,
        }),
        Animated.timing(shimmer, {
          toValue: 0,
          duration: 900,
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [shimmer]);

  const opacity = shimmer.interpolate({
    inputRange: [0, 1],
    outputRange: [0.4, 0.85],
  });

  return (
    <Animated.View style={[styles.card, styles.skeletonCard, { opacity }]}>
      <View style={[styles.thumbnailWrapper, styles.skeletonThumb]} />
      <View style={[styles.cardBody, styles.skeletonBody]}>
        <View style={styles.skeletonLineWide} />
        <View style={styles.skeletonLine} />
        <View style={styles.skeletonLine} />
        <View style={styles.skeletonPrice} />
      </View>
    </Animated.View>
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
  filterButton: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  filterButtonActive: {
    borderColor: "#2563eb",
    backgroundColor: "#eff6ff",
  },
  filterButtonText: {
    fontWeight: "600",
    color: "#111827",
  },
  filterButtonTextActive: {
    color: "#2563eb",
  },
  filterSummary: {
    paddingHorizontal: 20,
    color: "#2563eb",
    marginTop: 8,
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
  footer: {
    paddingVertical: 20,
    alignItems: "center",
  },
  footerText: {
    color: "#9ca3af",
  },
  skeletonContainer: {
    gap: 12,
  },
  skeletonCard: {
    backgroundColor: "#f3f4f6",
  },
  skeletonThumb: {
    backgroundColor: "#e5e7eb",
  },
  skeletonBody: {
    gap: 8,
    justifyContent: "center",
  },
  skeletonLine: {
    height: 12,
    backgroundColor: "#d1d5db",
    borderRadius: 6,
    width: "60%",
  },
  skeletonLineWide: {
    height: 16,
    backgroundColor: "#d1d5db",
    borderRadius: 6,
    width: "80%",
  },
  skeletonPrice: {
    height: 14,
    width: "40%",
    backgroundColor: "#cbd5f5",
    borderRadius: 6,
  },
});
