import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  FlatList,
  Image,
  Platform,
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
import { colors, radius, shadows, spacing } from "../theme/tokens";
import { ui } from "../theme/components";

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

  const formatPrice = (value?: number) => {
    if (typeof value === "number") {
      const rounded = Number.isInteger(value) ? value : value.toFixed(2);
      return `£${rounded}`;
    }
    return "Price TBD";
  };

  const renderItem = ({ item }: { item: DraftSummary }) => {
    const snippet = ((item as any).description as string | undefined) || "";
    const thumbUrl =
      (item as any).thumbnail_url_2x ||
      (item as any).thumbnail_url ||
      (item as any).cover_photo_url ||
      item.thumbnail_url ||
      null;
    const photos = thumbUrl ? [thumbUrl] : [];
    const placeholders = ["#dbeafe", "#e5e7eb", "#e0e7ff"];

    return (
      <TouchableOpacity
        style={styles.card}
        activeOpacity={0.85}
        onPress={() => navigation.navigate("DraftDetail", { id: item.id })}
      >
        <View style={styles.cardContent}>
          <View style={styles.thumbColumn}>
            {(photos.length ? photos : placeholders).slice(0, 2).map((thumb, idx) =>
              photos.length ? (
                <Image key={idx} source={{ uri: thumb as string }} style={styles.thumb} />
              ) : (
                <View key={idx} style={[styles.thumb, { backgroundColor: thumb as string }]} />
              )
            )}
            {item.photo_count ? (
              <View style={styles.photoBadge}>
                <Text style={styles.photoBadgeText}>
                  {item.photo_count} photo{item.photo_count > 1 ? "s" : ""}
                </Text>
              </View>
            ) : null}
          </View>
          <View style={styles.cardBody}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle} numberOfLines={1}>
                {item.title || "Untitled draft"}
              </Text>
              <StatusChip status={item.status} />
            </View>
            <View style={styles.pillRow}>
              <AttributePill label={item.brand || "Brand ?"} />
              <AttributePill label={item.size || "Size ?"} />
              <AttributePill label={item.colour || "Colour ?"} />
            </View>
            {item.condition ? (
              <Text style={styles.meta} numberOfLines={1}>
                Condition: {item.condition}
              </Text>
            ) : (
              <Text style={styles.meta} numberOfLines={1}>
                Condition ?
              </Text>
            )}
            {snippet ? (
              <Text style={styles.snippet} numberOfLines={2}>
                {snippet}
              </Text>
            ) : (
              <Text style={styles.meta} numberOfLines={1}>
                No description yet.
              </Text>
            )}
            <View style={styles.priceRow}>
              <Text style={styles.price}>{formatPrice(item.price_mid)}</Text>
              {item.updated_at ? (
                <Text style={styles.badge}>Updated {item.updated_at}</Text>
              ) : null}
            </View>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={ui.screen}>
      <View style={styles.screen}>
        <FlatList
          data={drafts}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderItem}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          ItemSeparatorComponent={() => <View style={styles.listGap} />}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          onEndReached={onEndReached}
          onEndReachedThreshold={0.4}
          ListHeaderComponent={
            <View style={styles.listHeader}>
              <View style={styles.headingRow}>
                <View style={{ flex: 1, gap: spacing.xs }}>
                  <Text style={styles.heading}>Drafts</Text>
                  <Text style={styles.subheading}>
                    Clean cards with all your edits in one place.
                  </Text>
                </View>
                <View style={styles.headerButtons}>
                  <TouchableOpacity
                    style={ui.secondaryButton}
                    onPress={() => setSettingsOpen(true)}
                  >
                    <Text style={ui.secondaryButtonText}>Server</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={ui.primaryButton}
                    onPress={() => navigation.navigate("Upload")}
                  >
                    <Text style={ui.primaryButtonText}>Upload photos</Text>
                  </TouchableOpacity>
                </View>
              </View>
              <View style={styles.serverCard}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.serverLabel}>Current backend</Text>
                  <Text style={styles.serverValue}>
                    {baseUrl || "Not connected"}
                  </Text>
                </View>
              </View>
              <View style={styles.filterRow}>
                {FILTERS.map((option) => (
                  <TouchableOpacity
                    key={option.value}
                    style={[ui.pill, filter === option.value && ui.pillActive]}
                    onPress={() => setFilter(option.value)}
                  >
                    <Text
                      style={[
                        ui.pillText,
                        filter === option.value && ui.pillTextActive,
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
              {loading && <ActivityIndicator style={{ marginVertical: spacing.md }} />}
              {error ? <Text style={styles.error}>{error}</Text> : null}
            </View>
          }
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
      </View>
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

const AttributePill = ({ label }: { label: string }) => (
  <View style={styles.attributePill}>
    <Text style={styles.attributePillText}>{label}</Text>
  </View>
);

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
      <View style={styles.thumbRow}>
        <View style={[styles.thumb, styles.skeletonThumb]} />
        <View style={[styles.thumb, styles.skeletonThumb]} />
        <View style={[styles.thumb, styles.skeletonThumb]} />
      </View>
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
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xxl,
    gap: spacing.md,
  },
  listHeader: {
    gap: spacing.md,
    paddingTop: spacing.md,
  },
  headingRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.md,
  },
  heading: { ...ui.headingXL },
  subheading: { ...ui.subheading },
  headerButtons: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  serverCard: {
    ...ui.card,
  },
  serverLabel: {
    ...ui.helper,
    fontWeight: "700",
  },
  serverValue: {
    fontSize: 16,
    fontWeight: "700",
    marginTop: spacing.xs,
    color: colors.text,
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  filterButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.lg,
    backgroundColor: colors.card,
  },
  filterButtonActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  filterButtonText: {
    fontWeight: "600",
    color: colors.text,
  },
  filterButtonTextActive: {
    color: colors.accent,
  },
  filterSummary: {
    color: colors.accent,
    marginTop: -spacing.xs,
  },
  error: {
    backgroundColor: "#fef2f2",
    color: colors.danger,
    padding: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "#fecdd3",
  },
  listGap: { height: spacing.md },
  card: {
    ...ui.card,
    overflow: "hidden",
  },
  cardContent: {
    flexDirection: "row",
    gap: spacing.md,
  },
  thumbColumn: {
    width: 118,
    gap: spacing.xs,
  },
  thumbRow: {
    flexDirection: "row",
    gap: spacing.xs,
    padding: spacing.sm,
  },
  thumb: {
    flex: 1,
    height: 84,
    borderRadius: radius.md,
    backgroundColor: colors.background,
  },
  photoBadge: {
    position: "absolute",
    right: spacing.xs,
    top: spacing.xs,
    backgroundColor: "rgba(17,24,39,0.85)",
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: radius.pill,
  },
  photoBadgeText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 12,
  },
  cardBody: {
    flex: 1,
    gap: spacing.xs,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.sm,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: "800",
    flex: 1,
    color: colors.text,
  },
  meta: {
    ...ui.meta,
  },
  snippet: {
    color: colors.text,
  },
  priceRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.xs,
  },
  price: {
    fontWeight: "800",
    fontSize: 17,
    color: colors.text,
  },
  badge: {
    backgroundColor: colors.accentMuted,
    color: colors.accent,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    fontSize: 12,
  },
  pillRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  attributePill: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: Platform.select({ ios: 6, default: 5 }),
  },
  attributePillText: {
    color: colors.text,
    fontWeight: "600",
    fontSize: 12,
  },
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.pill,
    minWidth: 72,
    alignItems: "center",
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
    fontWeight: "700",
    fontSize: 12,
  },
  empty: {
    padding: spacing.xl,
    alignItems: "center",
  },
  emptyText: {
    color: colors.muted,
    textAlign: "center",
  },
  footer: {
    paddingVertical: spacing.lg,
    alignItems: "center",
  },
  footerText: {
    color: colors.muted,
  },
  skeletonContainer: {
    gap: spacing.md,
  },
  skeletonCard: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  skeletonThumb: {
    backgroundColor: "#e5e7eb",
  },
  skeletonBody: {
    gap: spacing.sm,
    justifyContent: "center",
    paddingRight: spacing.md,
  },
  skeletonLine: {
    height: 12,
    backgroundColor: "#d1d5db",
    borderRadius: radius.sm,
    width: "60%",
  },
  skeletonLineWide: {
    height: 16,
    backgroundColor: "#d1d5db",
    borderRadius: radius.sm,
    width: "80%",
  },
  skeletonPrice: {
    height: 14,
    width: "40%",
    backgroundColor: "#cbd5f5",
    borderRadius: radius.sm,
  },
});
