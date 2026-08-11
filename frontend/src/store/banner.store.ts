import { create } from 'zustand';

interface BannerStore {
  active: boolean;
  message: string;
  /** Hex color, e.g. "#4f46e5" — null means "use the built-in default". */
  bgColor: string | null;
  textColor: string | null;
  isLoaded: boolean;
  setBanner: (active: boolean, message: string, bgColor: string | null, textColor: string | null) => void;
  setLoaded: () => void;
}

export const useBannerStore = create<BannerStore>()((set) => ({
  active: false,
  message: '',
  bgColor: null,
  textColor: null,
  isLoaded: false,

  setBanner: (active, message, bgColor, textColor) => set({ active, message, bgColor, textColor }),

  setLoaded: () => set({ isLoaded: true }),
}));

const _API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export async function checkBannerStatus(): Promise<void> {
  const store = useBannerStore.getState();
  try {
    const res = await fetch(`${_API_BASE}/site-settings/banner`, {
      credentials: 'include',
    });
    if (res.ok) {
      const data = await res.json();
      store.setBanner(!!data.active, data.message ?? '', data.bg_color ?? null, data.text_color ?? null);
    }
  } catch {
    // Network error — leave whatever state we had (fail safe: don't hide/show incorrectly)
  } finally {
    store.setLoaded();
  }
}
