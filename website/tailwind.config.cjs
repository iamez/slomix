/**
 * Build-time Tailwind config for the LEGACY frontend (website/index.html +
 * website/js/*.js). Replaces the runtime Play CDN (cdn.tailwindcss.com), whose
 * in-browser JIT compile dominated the main thread (Opus DevTools audit: ~71%,
 * LCP win). The theme.extend block mirrors website/js/tailwind-config.js exactly.
 *
 * The legacy JS builds some class names dynamically (`text-${c}-400`,
 * `bg-${c}-500/20`, `border-${accentColor}/30`, …), which a content-only purge
 * cannot see. The safelist below regenerates those combinations so no badge or
 * accent loses its colour. It is deliberately generous — the goal is killing the
 * runtime JIT, not a minimal stylesheet — but scoped to the prefixes/colours the
 * code actually interpolates.
 *
 * Rebuild after changing classes:  npm run build:css
 * (website/frontend is a SEPARATE React/Tailwind-v4 app — not covered here.)
 */
const COLORS = [
  'slate', 'red', 'green', 'blue', 'cyan', 'purple', 'emerald', 'rose',
  'amber', 'yellow', 'teal', 'orange', 'pink', 'indigo',
  'brand-blue', 'brand-cyan', 'brand-purple', 'brand-emerald', 'brand-rose',
  'brand-amber', 'brand-gold',
];

module.exports = {
  // Globs resolve relative to the CWD the CLI runs in (repo root via
  // `npm run build:css`), NOT this file's directory — so they are rooted at
  // website/, not bare ./index.html.
  content: [
    './website/index.html',
    './website/js/**/*.js',
  ],
  safelist: [
    {
      // dynamic color utilities: text-/bg-/border-/ring-/from-/to- with any
      // shade and the opacity steps the code uses
      pattern: new RegExp(
        `^(text|bg|border|ring|from|to|via|fill|stroke)-(${COLORS.join('|')})(-(300|400|500|600|700))?$`,
      ),
      variants: ['hover', 'group-hover', 'focus'],
    },
    {
      pattern: new RegExp(
        `^(text|bg|border|ring)-(${COLORS.join('|')})(-(300|400|500|600))?/(10|20|30|40|50|60|70|80|90)$`,
      ),
      variants: ['hover', 'group-hover'],
    },
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        reactor: ['Space Grotesk', 'sans-serif'],
        reactorMono: ['Space Mono', 'monospace'],
      },
      colors: {
        slate: { 850: '#151e2e', 900: '#0f172a', 950: '#020617' },
        brand: {
          blue: '#3b82f6',
          cyan: '#06b6d4',
          purple: '#8b5cf6',
          emerald: '#10b981',
          rose: '#f43f5e',
          amber: '#f59e0b',
          gold: '#fbbf24',
        },
      },
      backgroundImage: {
        'hero-pattern': 'radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 100% 0%, rgba(6, 182, 212, 0.1) 0%, transparent 50%)',
        'grid-pattern': 'linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
      },
    },
  },
  plugins: [],
};
