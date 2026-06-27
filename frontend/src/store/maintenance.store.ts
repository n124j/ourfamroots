import { create } from 'zustand';

interface MaintenanceStore {
  isMaintenanceMode: boolean;
  maintenanceMessage: string;
  isLoaded: boolean;
  setMaintenance: (enabled: boolean, message: string) => void;
  setLoaded: () => void;
}

export const useMaintenanceStore = create<MaintenanceStore>()((set) => ({
  isMaintenanceMode: false,
  maintenanceMessage: '',
  isLoaded: false,

  setMaintenance: (enabled, message) =>
    set({ isMaintenanceMode: enabled, maintenanceMessage: message }),

  setLoaded: () => set({ isLoaded: true }),
}));

const _API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export async function checkMaintenanceStatus(): Promise<void> {
  const store = useMaintenanceStore.getState();
  try {
    const res = await fetch(`${_API_BASE}/site-settings/maintenance`, {
      credentials: 'include',
    });
    if (res.ok) {
      const data = await res.json();
      store.setMaintenance(data.maintenance_mode, data.maintenance_message);
    }
  } catch {
    // Network error — assume site is up
  } finally {
    store.setLoaded();
  }
}
