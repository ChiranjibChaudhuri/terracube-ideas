import { create } from 'zustand';

export interface LayerConfig {
    id: string;
    name: string;
    type: 'dggs'; // Extensible
    data: string[]; // List of DGGIDs
    visible: boolean;
    opacity: number;
    origin?: 'dataset' | 'operation';
    cellCount?: number;
    color?: [number, number, number]; // Optional - if missing, use value-based coloring
    datasetId?: string;
    attrKey?: string;
    dggsName?: string;
    minValue?: number; // For color gradient range
    maxValue?: number; // For color gradient range
    colorRamp?: string; // Optional - name of the color ramp (e.g. "viridis", "magma")
}

export interface Annotation {
    id: string;
    cell_dggid: string;
    dataset_id: string;
    content: string;
    type: string;
    visibility: string;
    created_by?: string;
    created_at?: string;
}

interface AppState {
    layers: LayerConfig[];
    addLayer: (layer: LayerConfig) => void;
    updateLayer: (id: string, updates: Partial<LayerConfig>) => void;
    removeLayer: (id: string) => void;

    currentDatasetId: string | null;
    setCurrentDatasetId: (id: string | null) => void;

    currentTid: number;
    maxTid: number;
    setTid: (tid: number) => void;
    setMaxTid: (maxTid: number) => void;

    annotations: Annotation[];
    setAnnotations: (annotations: Annotation[]) => void;
    addAnnotation: (annotation: Annotation) => void;
    removeAnnotation: (id: string) => void;
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

    currentTid: 0,
    maxTid: 0,
    setTid: (tid) => set({ currentTid: tid }),
    setMaxTid: (maxTid) => set({ maxTid }),

    annotations: [],
    setAnnotations: (annotations) => set({ annotations }),
    addAnnotation: (annotation) => set((state) => ({ annotations: [annotation, ...state.annotations] })),
    removeAnnotation: (id) => set((state) => ({
        annotations: state.annotations.filter(a => a.id !== id)
    })),
}));
