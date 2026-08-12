/** @type {import('tailwindcss').Config} */
// Tokens are lifted verbatim from Implementation Blueprint Section 10.
// The risk-* colors are intentionally NOT part of the general palette naming
// (primary/surface/etc.) so a developer cannot reach for them decoratively by
// habit — in a clinical UI a color that means something must not also mean
// nothing elsewhere on the screen.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0E6E64", // deep clinical teal
          hover: "#0B5A52",
          soft: "#E6F1EF",
          50: "#F0F7F5",
          100: "#D7EBE7",
          400: "#2E9488",
          700: "#0B5A52",
          900: "#08403A",
        },
        accent: "#3B82C4", // supporting cool blue for data viz (never a risk color)
        // Marketing site: the two-tone story. Coral→crimson (the heart asset)
        // carries the human/emotional sections; teal (the dashboard) carries the
        // clinical sections. No third accent is introduced anywhere.
        coral: {
          DEFAULT: "#FB5779",
          light: "#FF7D96",
          deep: "#C4123A",
        },
        background: "#F5F8F7",
        surface: "#FFFFFF",
        text: {
          primary: "#101828",
          secondary: "#475467",
          tertiary: "#98A2B3",
        },
        border: "#E4E7EC",
        // Reserved EXCLUSIVELY for risk-band badges/indicators. Never decorative.
        risk: {
          low: "#12866F",
          moderate: "#B54708",
          high: "#B42318",
        },
      },
      backgroundImage: {
        "hero-mesh":
          "radial-gradient(at 0% 0%, #0E6E64 0px, transparent 55%), radial-gradient(at 98% 10%, #2E9488 0px, transparent 45%), radial-gradient(at 50% 100%, #08403A 0px, transparent 55%)",
        "primary-gradient": "linear-gradient(135deg, #0E6E64 0%, #12866F 55%, #2E9488 100%)",
        "coral-gradient": "linear-gradient(135deg, #FF7D96 0%, #FB5779 50%, #C4123A 100%)",
        "coral-text": "linear-gradient(120deg, #FB5779 0%, #C4123A 100%)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        // JetBrains Mono for vitals, lab values and percentages only — so
        // digits align and 0/O, 1/l don't get misread.
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
        // Marketing site type pairing (medical/trustworthy, per design tooling):
        // Figtree for display/headings, Noto Sans for body.
        display: ["Figtree", "Inter", "system-ui", "sans-serif"],
        body: ["'Noto Sans'", "Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        // Distinct radius language: 16px cards / 8px controls / pill badges.
        card: "16px",
        control: "8px",
      },
      spacing: {
        // 8pt grid.
        "card-padding": "24px",
        "section-padding": "32px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(16, 24, 40, 0.06), 0 1px 2px rgba(16, 24, 40, 0.04)",
        "card-hover": "0 4px 12px rgba(16, 24, 40, 0.08)",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        // One-time entrance only. No looping/ambient motion on clinical data
        // (Blueprint §10). Shimmer is used only on loading skeletons, which show
        // no data at all, so the "no ambient motion on clinical values" rule holds.
        "fade-in-up": "fade-in-up 0.35s ease-out both",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [],
};
