import { colors, radius, shadows, spacing } from "./tokens";

export const ui = {
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    ...shadows.card,
  },
  mutedCard: {
    backgroundColor: colors.background,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
  },
  headingXL: {
    fontSize: 28,
    fontWeight: "800",
    color: colors.text,
  },
  heading: {
    fontSize: 22,
    fontWeight: "700",
    color: colors.text,
  },
  subheading: {
    color: colors.muted,
    fontSize: 15,
  },
  label: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.text,
  },
  helper: {
    color: colors.muted,
    fontSize: 14,
  },
  meta: {
    color: colors.muted,
    fontSize: 13,
  },
  badge: {
    backgroundColor: colors.accentMuted,
    color: colors.accent,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.pill,
    fontWeight: "700",
    fontSize: 12,
  },
  pill: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.card,
  },
  pillActive: {
    backgroundColor: colors.accentMuted,
    borderColor: colors.accent,
  },
  pillText: {
    color: colors.text,
    fontWeight: "600",
  },
  pillTextActive: {
    color: colors.accent,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    fontSize: 16,
    backgroundColor: "#fff",
  },
  primaryButton: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  primaryButtonText: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 16,
  },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    backgroundColor: colors.card,
  },
  secondaryButtonText: {
    color: colors.text,
    fontWeight: "700",
    fontSize: 15,
  },
  divider: {
    borderBottomWidth: 1,
    borderColor: colors.border,
    marginVertical: spacing.md,
  },
} as const;

export type UIStyles = typeof ui;
