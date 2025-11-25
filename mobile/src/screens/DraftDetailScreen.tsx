import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  Image,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as Clipboard from "expo-clipboard";
import { DraftDetail, DraftStatus, fetchDraftDetail, updateDraft } from "../api";
import { useServer } from "../state/ServerContext";
import { RootStackParamList } from "../navigation/types";

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

export const DraftDetailScreen = ({ route }: Props) => {
  const { id } = route.params;
  const { baseUrl, uploadKey } = useServer();
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [status, setStatus] = useState<DraftStatus>("draft");
  const [copyMessage, setCopyMessage] = useState<string | null>(null);

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
      setPrice(
        current.selected_price?.toString() ||
          current.price_mid?.toString() ||
          ""
      );
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
      await updateDraft(
        baseUrl,
        draft.id,
        {
          title,
          description,
          status,
          price: parsedPrice,
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
              selected_price: parsedPrice ?? prev.selected_price,
            }
          : prev
      );
    } catch (err: any) {
      setError(err.message || "Unable to save draft.");
    } finally {
      setSaving(false);
    }
  }, [baseUrl, description, draft, price, status, title, uploadKey]);

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

  const body = loading ? (
    <ActivityIndicator style={{ marginTop: 40 }} />
  ) : (
    <ScrollView contentContainerStyle={styles.scroll}>
      {error && (
        <View style={styles.errorBlock}>
          <Text style={styles.error}>{error}</Text>
          <Button title="Retry" onPress={loadDraft} />
        </View>
      )}
      {draft?.photos?.length ? (
        <ScrollView horizontal contentContainerStyle={styles.photos}>
          {draft.photos.map((photo) => (
            <Image
              key={photo.id}
              source={{ uri: photo.url }}
              style={styles.photo}
            />
          ))}
        </ScrollView>
      ) : (
        <View style={styles.placeholderPhoto}>
          <Text style={styles.placeholderText}>No photos</Text>
        </View>
      )}
      <View style={styles.field}>
        <Text style={styles.label}>Title</Text>
        <TextInput
          style={styles.input}
          value={title}
          onChangeText={setTitle}
        />
      </View>
      <View style={styles.field}>
        <Text style={styles.label}>Description</Text>
        <TextInput
          style={[styles.input, styles.multiline]}
          multiline
          numberOfLines={4}
          value={description}
          onChangeText={setDescription}
        />
      </View>
      {priceSuggestions.length > 0 && (
        <View style={styles.priceSuggestions}>
          <Text style={styles.label}>Price suggestions</Text>
          <Text style={styles.helper}>
            Tap a suggestion to fill the price input below.
          </Text>
          <View style={styles.priceSuggestionRow}>
            {priceSuggestions.map((suggestion) => {
              const numeric = Number(price.trim());
              const isActive = !Number.isNaN(numeric) && numeric === suggestion.value;
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
          <TextInput
            style={styles.input}
            keyboardType="decimal-pad"
            value={price}
            onChangeText={setPrice}
            placeholder={priceValue ? String(priceValue) : "30"}
          />
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
                    status === option.value && styles.statusOptionTextActive,
                  ]}
                >
                  {option.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput
            style={styles.input}
            value={status}
            onChangeText={setStatus}
            placeholder="draft"
          />
          <Text style={styles.helper}>
            Tap a chip for quick status or type a custom state (e.g. posted).
          </Text>
        </View>
      </View>
      <View style={styles.field}>
        <Text style={styles.label}>Details</Text>
        <Text style={styles.meta}>
          Brand: {draft?.brand || "Unknown"} · Size: {draft?.size || "?"}
        </Text>
        <Text style={styles.meta}>
          Colour: {draft?.colour || "?"} · Condition:{" "}
          {draft?.condition || "Good"}
        </Text>
        {(draft?.price_low || draft?.price_high) && (
          <Text style={styles.meta}>
            Suggested price: £{draft?.price_low ?? "?"} - £
            {draft?.price_high ?? "?"} (mid £{draft?.price_mid ?? "?"})
          </Text>
        )}
      </View>
      <View style={styles.actions}>
        <Button
          title={saving ? "Saving..." : "Save changes"}
          onPress={onSave}
          disabled={saving}
        />
        <View style={{ height: 12 }} />
        <Button title="Post to Vinted" onPress={onPostHelper} />
        {copyMessage && <Text style={styles.helper}>{copyMessage}</Text>}
        <Text style={styles.helper}>
          Copies the title, description, and price to your clipboard, then opens
          (or reminds you to open) the Vinted app so you can paste the details.
        </Text>
      </View>
    </ScrollView>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>{body}</View>
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
    padding: 16,
  },
  scroll: {
    paddingBottom: 40,
    gap: 16,
  },
  photos: {
    gap: 12,
  },
  photo: {
    width: 200,
    height: 260,
    borderRadius: 12,
  },
  placeholderPhoto: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    height: 200,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderText: {
    color: "#9ca3af",
  },
  field: {
    gap: 4,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#374151",
  },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  multiline: {
    minHeight: 120,
    textAlignVertical: "top",
  },
  row: {
    flexDirection: "row",
    gap: 12,
  },
  flex: {
    flex: 1,
  },
  meta: {
    color: "#6b7280",
  },
  error: {
    backgroundColor: "#fef2f2",
    color: "#991b1b",
    padding: 12,
    borderRadius: 8,
  },
  errorBlock: {
    gap: 8,
  },
  statusRow: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap",
  },
  statusOption: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  statusOptionActive: {
    backgroundColor: "#111827",
    borderColor: "#111827",
  },
  statusOptionText: {
    color: "#374151",
    fontWeight: "600",
  },
  statusOptionTextActive: {
    color: "#fff",
  },
  actions: {
    gap: 8,
  },
  helper: {
    color: "#6b7280",
    fontSize: 14,
  },
  priceSuggestions: {
    gap: 8,
  },
  priceSuggestionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  priceSuggestionCard: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 12,
    padding: 12,
    width: 120,
    alignItems: "center",
    gap: 4,
  },
  priceSuggestionActive: {
    borderColor: "#2563eb",
    backgroundColor: "#eff6ff",
  },
  priceSuggestionLabel: {
    fontWeight: "600",
    color: "#111827",
  },
  priceSuggestionValue: {
    fontSize: 18,
    fontWeight: "700",
  },
});
