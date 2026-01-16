import { create } from 'zustand';

export interface LayerConfig {
    id: string;
    name: string;
    type: 'dggs'; // Extensible
    data: string[]; // List of DGGIDs
    visible: boolean;
    opacity: number;
    color: [number, number, number];
}

interface AppState {
    layers: LayerConfig[];
    addLayer: (layer: LayerConfig) => void;
    updateLayer: (id: string, updates: Partial<LayerConfig>) => void;
    removeLayer: (id: string) => void;

    currentDatasetId: string | null;
    setCurrentDatasetId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
    layers: [],
    addLayer: (layer) => set((state) => ({ layers: [...state.layers, layer] })),
    updateLayer: (id, updates) => set((state) => ({
        layers: state.layers.map(l => l.id === id ? { ...l, ...updates } : l)
    })),
    removeLayer: (id) => set((state) => ({
        layers: state.layers.filter(l => l.id !== id)
    })),

    currentDatasetId: null,
    setCurrentDatasetId: (id) => set({ currentDatasetId: id }),
}));
