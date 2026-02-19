/* global tailwind */
tailwind.config = {
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
                reactor: ['Space Grotesk', 'sans-serif'],
                reactorMono: ['Space Mono', 'monospace']
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
                    gold: '#fbbf24'
                }
            },
            backgroundImage: {
                'hero-pattern': "radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.15) 0%, transparent 50%), radial-gradient(circle at 100% 0%, rgba(6, 182, 212, 0.1) 0%, transparent 50%)",
                'grid-pattern': "linear-gradient(to right, rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.03) 1px, transparent 1px)"
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'float': 'float 6s ease-in-out infinite',
            },
            keyframes: {
                float: {
                    '0%, 100%': { transform: 'translateY(0)' },
                    '50%': { transform: 'translateY(-10px)' },
                }
            }
        }
    }
};
