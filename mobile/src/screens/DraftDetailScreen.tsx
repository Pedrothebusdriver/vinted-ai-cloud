import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  FlatList,
  KeyboardAvoidingView,
  Image,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as Clipboard from "expo-clipboard";
import { DraftDetail, DraftStatus, fetchDraftDetail, updateDraft } from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";
import { colors, radius, shadows, spacing } from "../theme/tokens";
import { ui } from "../theme/components";

type Props = NativeStackScreenProps<RootStackParamList, "DraftDetail">;

const FALLBACK_DRAFT: DraftDetail = {
  id: 0,
  title: "Sample draft",
  brand: "Nike",
  size: "M",
  colour: "Charcoal",
  status: "draft",
  description:
    "Comfy Nike Tech Fleece hoodie in charcoal grey. Hardly worn, great for layering.",
  price_mid: 55,
  photos: [
    {
      id: "sample",
      url: "https://images.unsplash.com/photo-1503341455253-b2e723bb3dbb?w=800",
    },
  ],
};

const STATUS_OPTIONS: { label: string; value: DraftStatus }[] = [
  { label: "Draft", value: "draft" },
  { label: "Ready", value: "ready" },
];

const CONDITION_OPTIONS = [
  { label: "New", value: "new" },
  { label: "Like new", value: "like new" },
  { label: "Good", value: "good" },
  { label: "Fair", value: "fair" },
];

const SummaryItem = ({ label, value }: { label: string; value: string }) => (
  <View style={styles.summaryItem}>
    <Text style={styles.summaryLabel}>{label}</Text>
    <Text style={styles.summaryValue} numberOfLines={1}>
      {value}
    </Text>
  </View>
);

export const DraftDetailScreen = ({ route }: Props) => {
  const { id } = route.params;
  const { baseUrl, uploadKey } = useServer();
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState<DraftStatus>("draft");
  const [brand, setBrand] = useState("");
  const [size, setSize] = useState("");
  const [colour, setColour] = useState("");
  const [condition, setCondition] = useState("");
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [photos, setPhotos] = useState<DraftDetail["photos"]>([]);
  const [coverId, setCoverId] = useState<string | number | null>(null);

  const priceValue = useMemo(() => {
    if (draft?.selected_price) return draft.selected_price;
    if (draft?.price_mid) return draft.price_mid;
    return null;
  }, [draft]);

  const syncForm = useCallback(
    (current: DraftDetail | null) => {
      if (!current) return;
      setTitle(current.title || "");
      setDescription(current.description || "");
      setStatus(current.status || "draft");
      setBrand(current.brand || "");
      setSize(current.size || "");
      setColour(current.colour || "");
      setCondition(current.condition || "");
      setPrice(
        current.selected_price?.toString() ||
          current.price_mid?.toString() ||
          ""
      );
      if (current.photos?.length) {
        setPhotos(current.photos);
        const coverMatch = current.cover_photo_url
          ? current.photos.find((p) => p.url === current.cover_photo_url)
          : current.photos[0];
        setCoverId(coverMatch?.id ?? current.photos[0]?.id ?? null);
      } else {
        setPhotos([]);
        setCoverId(null);
      }
    },
    []
  );

  const loadDraft = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchDraftDetail(baseUrl, id, {
        uploadKey,
      });
      setDraft(response);
      syncForm(response);
    } catch (err: any) {
      setError(err.message || "Unable to load draft. Showing sample data.");
      const sample = { ...FALLBACK_DRAFT, id };
      setDraft(sample);
      syncForm(sample);
    } finally {
      setLoading(false);
    }
  }, [baseUrl, id, syncForm, uploadKey]);

  useEffect(() => {
    loadDraft();
  }, [loadDraft]);

  const onSave = useCallback(async () => {
    if (!draft) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const parsedPrice = price.trim() ? Number(price.trim()) : undefined;
      const coverPhoto = photos.find((p) => p.id === coverId) || photos[0];
      await updateDraft(
        baseUrl,
        draft.id,
        {
          title,
          description,
          status,
          brand,
          size,
          colour,
          condition,
          price: parsedPrice,
          cover_photo_url: coverPhoto?.url || undefined,
          thumbnail_url: coverPhoto?.thumbnail_url || coverPhoto?.url || undefined,
          thumbnail_url_2x: coverPhoto?.thumbnail_url_2x || undefined,
        },
        { uploadKey }
      );
      setDraft((prev) =>
        prev
          ? {
              ...prev,
              title,
              description,
              status,
              brand,
              size,
              colour,
              condition,
              selected_price: parsedPrice ?? prev.selected_price,
              cover_photo_url: coverPhoto?.url || prev.cover_photo_url,
              thumbnail_url: coverPhoto?.thumbnail_url || coverPhoto?.url || prev.thumbnail_url,
              thumbnail_url_2x: coverPhoto?.thumbnail_url_2x || prev.thumbnail_url_2x,
            }
          : prev
      );
    } catch (err: any) {
      setError(err.message || "Unable to save draft.");
    } finally {
      setSaving(false);
    }
  }, [
    baseUrl,
    brand,
    colour,
    condition,
    description,
    draft,
    coverId,
    photos,
    price,
    size,
    status,
    title,
    uploadKey,
  ]);

  const onPostHelper = useCallback(async () => {
    if (!draft) return;
    setCopyMessage(null);
    const priceDisplay = price.trim()
      ? price.trim()
      : priceValue
      ? String(priceValue)
      : "";
    const helperText = `${title || draft.title}\n\n${
      description || draft.description || ""
    }\n\nPrice: ${priceDisplay ? `£${priceDisplay}` : "TBD"}`.trim();
    try {
      await Clipboard.setStringAsync(helperText);
      const deepLink = "vinted://items/new";
      const supported = await Linking.canOpenURL(deepLink);
      if (supported) {
        await Linking.openURL(deepLink);
        setCopyMessage("Copied listing text. Opening Vinted...");
      } else {
        Alert.alert(
          "Copied to clipboard",
          "We copied the listing text. Open the Vinted app, tap the + button, and paste the details into your draft. If Vinted isn't installed, install it from the App Store first."
        );
        setCopyMessage("Copied listing text for manual paste into Vinted.");
      }
    } catch (err: any) {
      Alert.alert("Clipboard failed", err?.message || "Unable to copy listing text.");
    }
  }, [description, draft, price, priceValue, title]);

  const priceSuggestions = useMemo(() => {
    if (!draft) return [];
    const entries: { label: string; value: number }[] = [];
    if (typeof draft.price_low === "number") {
      entries.push({ label: "Low", value: draft.price_low });
    }
    if (typeof draft.price_mid === "number") {
      entries.push({ label: "Mid", value: draft.price_mid });
    }
    if (typeof draft.price_high === "number") {
      entries.push({ label: "High", value: draft.price_high });
    }
    return entries;
  }, [draft]);

  const onSelectSuggestedPrice = useCallback(
    (value: number) => {
      setPrice(String(value));
    },
    [setPrice]
  );

  const onSelectCover = useCallback(
    (photo: DraftDetail["photos"][number]) => {
      setCoverId(photo.id);
      setPhotos((prev) => {
        const rest = prev.filter((p) => p.id !== photo.id);
        return [photo, ...rest];
      });
    },
    []
  );

  return (
    <SafeAreaView style={ui.screen}>
      <KeyboardAvoidingView
        style={ui.screen}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 60 : 0}
      >
        <View style={styles.container}>
          {loading ? (
            <ActivityIndicator style={{ marginTop: 40 }} />
          ) : (
            <ScrollView
              keyboardShouldPersistTaps="handled"
              contentContainerStyle={[
                styles.scroll,
                { paddingBottom: spacing.xxl + insets.bottom + 100 },
              ]}
              showsVerticalScrollIndicator={false}
            >
              {error && (
                <View style={styles.errorBlock}>
                  <Text style={styles.error}>{error}</Text>
                  <Button title="Retry" onPress={loadDraft} />
                </View>
              )}
              {photos?.length ? (
                <FlatList
                  data={photos}
                  horizontal
                  keyExtractor={(photo) => String(photo.id)}
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.photos}
                  renderItem={({ item }) => {
                    const isCover = coverId === item.id;
                    return (
                      <TouchableOpacity
                        activeOpacity={0.85}
                        onPress={() => onSelectCover(item)}
                        style={[styles.photoCard, isCover && styles.coverPhoto]}
                      >
                        <Image
                          source={{ uri: item.thumbnail_url || item.url }}
                          style={styles.photo}
                        />
                        <View style={styles.photoFooter}>
                          <Text style={styles.photoFilename} numberOfLines={1}>
                            {item.filename || item.id}
                          </Text>
                          <Text style={styles.photoAction}>
                            {isCover ? "Cover" : "Set as cover"}
                          </Text>
                        </View>
                      </TouchableOpacity>
                    );
                  }}
                />
              ) : (
                <View style={styles.placeholderPhoto}>
                  <Text style={styles.placeholderText}>No photos</Text>
                </View>
              )}
              {draft && (
                <View style={styles.summaryRow}>
                  <SummaryItem label="Brand" value={brand || draft.brand || "—"} />
                  <SummaryItem label="Size" value={size || draft.size || "—"} />
                  <SummaryItem label="Colour" value={colour || draft.colour || "—"} />
                  <SummaryItem
                    label="Price"
                    value={
                      priceValue
                        ? `£${priceValue}`
                        : draft.price_low || draft.price_high
                        ? `£${draft.price_low ?? "?"} - £${draft.price_high ?? "?"}`
                        : "TBD"
                    }
                  />
                </View>
              )}

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Listing details</Text>
                <View style={styles.field}>
                  <Text style={styles.label}>Title</Text>
                  <TextInput
                    style={styles.input}
                    value={title}
                    onChangeText={setTitle}
                    placeholder="Listing title"
                  />
                </View>
                <View style={styles.field}>
                  <Text style={styles.label}>Description</Text>
                  <TextInput
                    style={[styles.input, styles.multiline]}
                    multiline
                    numberOfLines={6}
                    value={description}
                    onChangeText={setDescription}
                    placeholder="Describe the item, fit, and condition."
                  />
                </View>
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Attributes</Text>
                <View style={styles.row}>
                  <View style={[styles.field, styles.flex]}>
                    <Text style={styles.label}>Brand</Text>
                    <TextInput
                      style={styles.input}
                      value={brand}
                      onChangeText={setBrand}
                      placeholder="Zara / Nike"
                    />
                  </View>
                  <View style={[styles.field, styles.flex]}>
                    <Text style={styles.label}>Size</Text>
                    <TextInput
                      style={styles.input}
                      value={size}
                      onChangeText={setSize}
                      placeholder="M / UK 10"
                    />
                  </View>
                </View>
                <View style={styles.row}>
                  <View style={[styles.field, styles.flex]}>
                    <Text style={styles.label}>Colour</Text>
                    <TextInput
                      style={styles.input}
                      value={colour}
                      onChangeText={setColour}
                      placeholder="Charcoal"
                    />
                  </View>
                  <View style={[styles.field, styles.flex]}>
                    <Text style={styles.label}>Condition</Text>
                    <View style={styles.statusRow}>
                      {CONDITION_OPTIONS.map((option) => (
                        <TouchableOpacity
                          key={option.value}
                          style={[
                            styles.statusOption,
                            condition.toLowerCase() === option.value &&
                              styles.statusOptionActive,
                          ]}
                          onPress={() => setCondition(option.value)}
                        >
                          <Text
                            style={[
                              styles.statusOptionText,
                              condition.toLowerCase() === option.value &&
                                styles.statusOptionTextActive,
                            ]}
                          >
                            {option.label}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    <TextInput
                      style={styles.input}
                      value={condition}
                      onChangeText={setCondition}
                      placeholder="Good"
                    />
                  </View>
                </View>
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Pricing</Text>
                {priceSuggestions.length > 0 && (
                  <View style={styles.priceSuggestions}>
                    <Text style={styles.helper}>
                      Tap a suggestion to fill the price input below.
                    </Text>
                    <View style={styles.priceSuggestionRow}>
                      {priceSuggestions.map((suggestion) => {
                        const numeric = Number(price.trim());
                        const isActive =
                          !Number.isNaN(numeric) && numeric === suggestion.value;
                        return (
                          <TouchableOpacity
                            key={suggestion.label}
                            style={[
                              styles.priceSuggestionCard,
                              isActive && styles.priceSuggestionActive,
                            ]}
                            onPress={() => onSelectSuggestedPrice(suggestion.value)}
                          >
                            <Text style={styles.priceSuggestionLabel}>
                              {suggestion.label}
                            </Text>
                            <Text style={styles.priceSuggestionValue}>
                              £{suggestion.value}
                            </Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  </View>
                )}
                <View style={styles.row}>
                  <View style={[styles.field, styles.flex]}>
                    <Text style={styles.label}>Price (£)</Text>
                    <View style={styles.inputWithAddon}>
                      <Text style={styles.inputAddon}>£</Text>
                      <TextInput
                        style={[styles.input, styles.inputFlex]}
                        keyboardType="decimal-pad"
                        value={price}
                        onChangeText={setPrice}
                        placeholder={priceValue ? String(priceValue) : "30"}
                      />
                    </View>
                  </View>
                  <View style={[styles.field, styles.flex]}>
                    <Text style={styles.label}>Status</Text>
                    <View style={styles.statusRow}>
                      {STATUS_OPTIONS.map((option) => (
                        <TouchableOpacity
                          key={option.value}
                          style={[
                            styles.statusOption,
                            status === option.value && styles.statusOptionActive,
                          ]}
                          onPress={() => setStatus(option.value)}
                        >
                          <Text
                            style={[
                              styles.statusOptionText,
                              status === option.value &&
                                styles.statusOptionTextActive,
                            ]}
                          >
                            {option.label}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                </View>
                {(draft?.price_low || draft?.price_high) && (
                  <Text style={styles.meta}>
                    Suggested price: £{draft?.price_low ?? "?"} - £
                    {draft?.price_high ?? "?"} (mid £{draft?.price_mid ?? "?"})
                  </Text>
                )}
              </View>

              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Helper</Text>
                <Text style={styles.meta}>
                  Brand: {brand || "Unknown"} · Size: {size || "?"}
                </Text>
                <Text style={styles.meta}>
                  Colour: {colour || "?"} · Condition: {condition || "Good"}
                </Text>
                {copyMessage && <Text style={styles.helper}>{copyMessage}</Text>}
                <Text style={styles.helper}>
                  Copies the title, description, and price, then opens Vinted (if
                  installed) so you can paste the details.
                </Text>
              </View>
            </ScrollView>
          )}
          <View
            style={[
              styles.footerBar,
              { paddingBottom: spacing.lg + insets.bottom },
            ]}
          >
            <TouchableOpacity
              style={[
                ui.primaryButton,
                styles.footerButton,
                saving && styles.disabledButton,
              ]}
              onPress={onSave}
              disabled={saving}
              activeOpacity={0.85}
            >
              <Text style={ui.primaryButtonText}>
                {saving ? "Saving..." : "Save changes"}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[ui.secondaryButton, styles.footerButton]}
              onPress={onPostHelper}
              activeOpacity={0.85}
            >
              <Text style={ui.secondaryButtonText}>Post to Vinted</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    padding: spacing.xl,
    gap: spacing.lg,
  },
  photos: {
    gap: spacing.sm,
  },
  photoCard: {
    ...ui.card,
    padding: 0,
    marginRight: spacing.sm,
    overflow: "hidden",
  },
  coverPhoto: {
    borderColor: colors.accent,
  },
  photo: {
    width: 230,
    height: 270,
  },
  coverBadge: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    backgroundColor: "rgba(37, 99, 235, 0.9)",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
  },
  coverBadgeText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 12,
  },
  photoFooter: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  photoFilename: { ...ui.meta },
  photoAction: {
    color: colors.accent,
    fontWeight: "700",
  },
  placeholderPhoto: {
    ...ui.card,
    height: 220,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderText: {
    color: colors.muted,
  },
  summaryRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  summaryItem: {
    flexBasis: "48%",
    borderRadius: radius.md,
    padding: spacing.md,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryLabel: { ...ui.meta },
  summaryValue: {
    fontWeight: "700",
    fontSize: 16,
    color: colors.text,
    marginTop: 2,
  },
  card: {
    ...ui.card,
    gap: spacing.md,
  },
  sectionTitle: { ...ui.heading },
  field: {
    gap: spacing.xs,
  },
  label: { ...ui.label },
  input: {
    ...ui.input,
  },
  multiline: {
    minHeight: 140,
    textAlignVertical: "top",
  },
  row: {
    flexDirection: "row",
    gap: spacing.md,
  },
  flex: {
    flex: 1,
  },
  meta: { ...ui.meta },
  error: {
    backgroundColor: "#fef2f2",
    color: colors.danger,
    padding: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "#fecdd3",
  },
  errorBlock: {
    gap: spacing.sm,
  },
  statusRow: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
  },
  statusOption: { ...ui.pill },
  statusOptionActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  statusOptionText: {
    color: colors.text,
    fontWeight: "600",
  },
  statusOptionTextActive: {
    color: "#fff",
  },
  helper: { ...ui.helper },
  priceSuggestions: {
    gap: spacing.sm,
  },
  priceSuggestionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
  },
  priceSuggestionCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    width: 120,
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.card,
  },
  priceSuggestionActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  priceSuggestionLabel: {
    fontWeight: "600",
    color: colors.text,
  },
  priceSuggestionValue: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.text,
  },
  inputWithAddon: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
  },
  inputAddon: {
    backgroundColor: colors.background,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.muted,
  },
  inputFlex: {
    flex: 1,
  },
  footerBar: {
    flexDirection: "row",
    gap: spacing.sm,
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
  disabledButton: {
    opacity: 0.65,
  },
});
