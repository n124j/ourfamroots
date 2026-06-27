import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface CanvasTheme {
  preset: string;
  canvasBg: string;
  canvasDot: string;
  nodeBg: string;
  nodeBorder: string;
  nodeText: string;
  nodeSubtext: string;
  nodeHoverBg: string;
  edgeColor: string;
  edgeWidth: number;
  edgeHighlight: string;
}

export const THEME_PRESETS: CanvasTheme[] = [
  {
    preset: 'classic',
    canvasBg: '#f8fafc', canvasDot: '#e2e8f0',
    nodeBg: '#ffffff', nodeBorder: '#e2e8f0',
    nodeText: '#1e293b', nodeSubtext: '#64748b', nodeHoverBg: '#f1f5f9',
    edgeColor: '#94a3b8', edgeWidth: 1.5, edgeHighlight: '#3b82f6',
  },
  {
    preset: 'dark',
    canvasBg: '#0f172a', canvasDot: '#1e293b',
    nodeBg: '#1e293b', nodeBorder: '#334155',
    nodeText: '#f1f5f9', nodeSubtext: '#94a3b8', nodeHoverBg: '#273549',
    edgeColor: '#475569', edgeWidth: 1.5, edgeHighlight: '#818cf8',
  },
  {
    preset: 'warm',
    canvasBg: '#fdf8f0', canvasDot: '#e8d5c0',
    nodeBg: '#fffbf5', nodeBorder: '#e8d5c0',
    nodeText: '#3d2b1f', nodeSubtext: '#8b6f5e', nodeHoverBg: '#f5ede0',
    edgeColor: '#c4956a', edgeWidth: 1.5, edgeHighlight: '#d97706',
  },
  {
    preset: 'blueprint',
    canvasBg: '#0c1a2e', canvasDot: '#1e3a5f',
    nodeBg: '#0f2744', nodeBorder: '#1e3a5f',
    nodeText: '#e2f0ff', nodeSubtext: '#7cb4d6', nodeHoverBg: '#173352',
    edgeColor: '#4a90b8', edgeWidth: 1.5, edgeHighlight: '#63b3ed',
  },
  {
    preset: 'forest',
    canvasBg: '#f0f7f0', canvasDot: '#c8dfc8',
    nodeBg: '#f5fbf5', nodeBorder: '#c8dfc8',
    nodeText: '#1a3320', nodeSubtext: '#4a7a54', nodeHoverBg: '#e5f2e5',
    edgeColor: '#5a9a6a', edgeWidth: 1.5, edgeHighlight: '#2d7a3a',
  },
];

export const PRESET_LABEL: Record<string, string> = {
  classic: 'Classic', dark: 'Dark', warm: 'Warm',
  blueprint: 'Blueprint', forest: 'Forest', custom: 'Custom',
};

interface ThemeStore {
  theme: CanvasTheme;
  setPreset: (name: string) => void;
  updateField: <K extends keyof CanvasTheme>(field: K, value: CanvasTheme[K]) => void;
  reset: () => void;
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: THEME_PRESETS[0],
      setPreset: (name) => {
        const p = THEME_PRESETS.find((t) => t.preset === name);
        if (p) set({ theme: p });
      },
      updateField: (field, value) =>
        set((s) => ({ theme: { ...s.theme, preset: 'custom', [field]: value } })),
      reset: () => set({ theme: THEME_PRESETS[0] }),
    }),
    { name: 'fr:canvas-theme' }
  )
);
