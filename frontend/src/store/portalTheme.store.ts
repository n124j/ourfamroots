import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface PortalTheme {
  preset: string;
  mainBg: string;
  sidebarBg: string;
  sidebarBorder: string;
  navText: string;
  navHover: string;
  navActiveBg: string;
  navActiveText: string;
  logoText: string;
  cardBg: string;
  textPrimary: string;
  textMuted: string;
}

export const PORTAL_PRESETS: PortalTheme[] = [
  {
    preset: 'light',
    mainBg: '#f8fafc', sidebarBg: '#ffffff', sidebarBorder: '#e5e7eb',
    navText: '#4b5563', navHover: '#f3f4f6',
    navActiveBg: '#eff6ff', navActiveText: '#1d4ed8',
    logoText: '#4f46e5', cardBg: '#ffffff',
    textPrimary: '#111827', textMuted: '#6b7280',
  },
  {
    preset: 'dark',
    mainBg: '#0f172a', sidebarBg: '#1e293b', sidebarBorder: '#334155',
    navText: '#94a3b8', navHover: '#334155',
    navActiveBg: '#3730a3', navActiveText: '#a5b4fc',
    logoText: '#a5b4fc', cardBg: '#1e293b',
    textPrimary: '#f1f5f9', textMuted: '#94a3b8',
  },
  {
    preset: 'warm',
    mainBg: '#fdf8f0', sidebarBg: '#fffbf5', sidebarBorder: '#e8d5c0',
    navText: '#78523b', navHover: '#f5ede0',
    navActiveBg: '#fef3c7', navActiveText: '#b45309',
    logoText: '#b45309', cardBg: '#fffbf5',
    textPrimary: '#3d2b1f', textMuted: '#8b6f5e',
  },
  {
    preset: 'slate',
    mainBg: '#f1f5f9', sidebarBg: '#0f172a', sidebarBorder: '#1e293b',
    navText: '#94a3b8', navHover: '#1e293b',
    navActiveBg: '#0284c7', navActiveText: '#f0f9ff',
    logoText: '#38bdf8', cardBg: '#ffffff',
    textPrimary: '#0f172a', textMuted: '#64748b',
  },
  {
    preset: 'forest',
    mainBg: '#f0f7f0', sidebarBg: '#1a3320', sidebarBorder: '#2d5a3a',
    navText: '#86c994', navHover: '#2d5a3a',
    navActiveBg: '#14532d', navActiveText: '#bbf7d0',
    logoText: '#4ade80', cardBg: '#f5fbf5',
    textPrimary: '#1a3320', textMuted: '#4a7a54',
  },
];

export const PORTAL_PRESET_LABEL: Record<string, string> = {
  light: 'Light', dark: 'Dark', warm: 'Warm',
  slate: 'Slate', forest: 'Forest', custom: 'Custom',
};

interface PortalThemeStore {
  theme: PortalTheme;
  setPreset: (name: string) => void;
  updateField: <K extends keyof PortalTheme>(field: K, value: PortalTheme[K]) => void;
  reset: () => void;
}

export const usePortalThemeStore = create<PortalThemeStore>()(
  persist(
    (set) => ({
      theme: PORTAL_PRESETS[0],
      setPreset: (name) => {
        const p = PORTAL_PRESETS.find((t) => t.preset === name);
        if (p) set({ theme: p });
      },
      updateField: (field, value) =>
        set((s) => ({ theme: { ...s.theme, preset: 'custom', [field]: value } })),
      reset: () => set({ theme: PORTAL_PRESETS[0] }),
    }),
    { name: 'fr:portal-theme' }
  )
);
