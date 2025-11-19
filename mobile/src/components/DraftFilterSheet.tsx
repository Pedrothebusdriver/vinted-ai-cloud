import { useEffect, useState } from "react";
import {
  Button,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  TouchableWithoutFeedback,
  View,
} from "react-native";

export type FilterOption = {
  label: string;
  value: string;
};

type Props = {
  visible: boolean;
  status: string;
  statusOptions: FilterOption[];
  onStatusChange: (value: string) => void;
  brand?: string;
  size?: string;
  onApply: (filters: { brand?: string; size?: string }) => void;
  onClear: () => void;
  onClose: () => void;
};

export const DraftFilterSheet = ({
  visible,
  status,
  statusOptions,
  onStatusChange,
  brand,
  size,
  onApply,
  onClear,
  onClose,
}: Props) => {
  const [localBrand, setLocalBrand] = useState(brand || "");
  const [localSize, setLocalSize] = useState(size || "");

  useEffect(() => {
    if (visible) {
      setLocalBrand(brand || "");
      setLocalSize(size || "");
    }
  }, [visible, brand, size]);

  const applyFilters = () => {
    onApply({
      brand: localBrand.trim() || undefined,
      size: localSize.trim() || undefined,
    });
    onClose();
  };

  const clearFilters = () => {
    setLocalBrand("");
    setLocalSize("");
    onClear();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <TouchableWithoutFeedback onPress={onClose}>
        <View style={styles.overlay} />
      </TouchableWithoutFeedback>
      <View style={styles.sheet}>
        <View style={styles.handle} />
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={styles.title}>Filters</Text>
          <Text style={styles.subtitle}>
            Filter drafts by status, brand, or size.
          </Text>
          <View style={styles.section}>
            <Text style={styles.label}>Status</Text>
            <View style={styles.chips}>
              {statusOptions.map((option) => (
                <TouchableOpacity
                  key={option.value}
                  style={[
                    styles.chip,
                    status === option.value && styles.chipActive,
                  ]}
                  onPress={() => onStatusChange(option.value)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      status === option.value && styles.chipTextActive,
                    ]}
                  >
                    {option.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={styles.section}>
            <Text style={styles.label}>Brand</Text>
            <TextInput
              style={styles.input}
              value={localBrand}
              onChangeText={setLocalBrand}
              placeholder="Nike, Zara…"
            />
          </View>
          <View style={styles.section}>
            <Text style={styles.label}>Size</Text>
            <TextInput
              style={styles.input}
              value={localSize}
              onChangeText={setLocalSize}
              placeholder="M / UK 10 / W32"
            />
          </View>
          <View style={styles.actions}>
            <Button title="Clear" onPress={clearFilters} />
            <Button title="Apply" onPress={applyFilters} />
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  sheet: {
    flex: 1,
    justifyContent: "flex-end",
  },
  handle: {
    width: 60,
    height: 6,
    borderRadius: 999,
    backgroundColor: "#d1d5db",
    alignSelf: "center",
    marginVertical: 12,
  },
  content: {
    backgroundColor: "#fff",
    paddingHorizontal: 24,
    paddingBottom: 32,
    gap: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: "700",
  },
  subtitle: {
    color: "#6b7280",
  },
  section: {
    gap: 8,
  },
  label: {
    fontWeight: "600",
    color: "#111827",
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  chipActive: {
    backgroundColor: "#111827",
    borderColor: "#111827",
  },
  chipText: {
    color: "#374151",
    fontWeight: "600",
  },
  chipTextActive: {
    color: "#fff",
  },
  input: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 10,
    padding: 12,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 16,
    marginTop: 8,
  },
});
