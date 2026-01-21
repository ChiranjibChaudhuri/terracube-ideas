import React, { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, MapView as DeckMapView } from '@deck.gl/core';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { resolveZonePolygons } from '../lib/dggal';
import { useAppStore, type LayerConfig } from '../lib/store';
import { useDatasets } from '../lib/api-hooks';
import { fetchCells } from '../lib/api';
import { LayerList } from '../components/LayerList';
import { ToolboxPanel } from '../components/ToolboxPanel';

// Initial View State (North America focus for demo)
const INITIAL_VIEW_STATE = {
    longitude: -95,
    latitude: 50,
    zoom: 3,
    pitch: 0,
    bearing: 0
};

const BASEMAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

// Create explicit MapView for proper geographic coordinate interpretation
const DECK_VIEW = new DeckMapView({ id: 'main-map', repeat: true });

export default function Workbench() {
    const { layers, addLayer } = useAppStore();
    const { data: datasets = [] } = useDatasets();

    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [layerPolygons, setLayerPolygons] = useState<Record<string, { polygon: number[][]; dggid: string }[]>>({});

    useEffect(() => {
        let active = true;
        const buildPolygons = async () => {
            const next: Record<string, { polygon: number[][]; dggid: string }[]> = {};
            for (const layer of layers) {
                if (!layer.visible) continue;
                const polygonMap = await resolveZonePolygons(layer.data, 3, {
                    concurrency: 12,
                    dggsName: layer.dggsName
                });
                next[layer.id] = layer.data.flatMap((dggid: string) => {
                    const polygon = polygonMap.get(dggid);
                    return polygon ? [{ polygon, dggid }] : [];
                });

            }
            if (active) {
                setLayerPolygons(next);
            }
        };

        buildPolygons().catch(() => undefined);
        return () => {
            active = false;
        };
    }, [layers]);

    // Transform store configs to DeckGL layers
    const deckLayers = useMemo(() => {
        return layers.map((l: LayerConfig) => {
            if (!l.visible) return null;
            return new PolygonLayer({
                id: l.id,
                data: layerPolygons[l.id] ?? [],
                getPolygon: (d: { polygon: number[][] }) => d.polygon,
                getFillColor: [...l.color, l.opacity * 255] as [number, number, number, number],
                stroked: true,
                getLineColor: [0, 0, 0, 100] as [number, number, number, number],
                lineWidthMinPixels: 1,
                pickable: true,
                // Explicitly set coordinate system to interpret [lon, lat] as geographic degrees
                coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
            });
        }).filter(Boolean);
    }, [layers, layerPolygons]);

    const loadDemoLayer = async (datasetId: string, name: string, attrKey?: string, dggsName?: string) => {
        try {
            const result = await fetchCells(datasetId, {
                key: attrKey,
                limit: '5000'
            });
            const cells = result.cells ?? [];
            const dggids = cells.map((cell: { dggid: string }) => cell.dggid);
            addLayer({
                id: `demo-${datasetId}-${Date.now()}`,
                name: name,
                type: 'dggs',
                data: dggids,
                visible: true,
                opacity: 0.5,
                color: [0, 255, 0],
                datasetId,
                attrKey,
                dggsName
            });
        } catch {
            // Intentionally silent for now; UI already shows empty state when datasets are missing.
        }
    };

    return (
        <div className="page workbench">
            <div className="workbench-shell">
                {/* Sidebar */}
                <aside className={`workbench-sidebar ${isSidebarOpen ? 'open' : 'collapsed'}`}>
                    <div className="workbench-sidebar__header">
                        {isSidebarOpen && <span className="workbench-sidebar__title">DGGS ANALYST</span>}
                        <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="workbench-sidebar__toggle">
                            {isSidebarOpen ? '«' : '»'}
                        </button>
                    </div>

                    {isSidebarOpen && (
                        <div className="workbench-sidebar__content">
                            {/* Datasets Section */}
                            <div className="section">
                                <div className="section-title">Available Datasets</div>
                                <div className="dataset-list">
                                    {datasets.map((ds: any) => (
                                        <button
                                            key={ds.id}
                                            onClick={() => loadDemoLayer(ds.id, ds.name, ds.metadata?.attr_key, ds.dggs_name)}
                                            className="dataset-item"
                                        >
                                            <span className="dataset-item__name">{ds.name}</span>
                                            <span className="dataset-item__add">+</span>
                                        </button>
                                    ))}
                                    {datasets.length === 0 && (
                                        <div className="empty-state">No datasets available. Start the backend to load demo data.</div>
                                    )}
                                </div>
                            </div>

                            {/* Layers Section */}
                            <div className="section">
                                <div className="section-title">Layers</div>
                                <LayerList />
                            </div>

                            {/* Toolbox Section */}
                            <div className="section">
                                <div className="section-title">Toolbox</div>
                                <ToolboxPanel />
                            </div>
                        </div>
                    )}
                </aside>

                {/* Map Panel */}
                <main className="workbench-map">
                    <div className="map-shell">
                        <DeckGL
                            initialViewState={INITIAL_VIEW_STATE}
                            controller={true}
                            layers={deckLayers}
                            views={DECK_VIEW}
                            getTooltip={({ object }) => object && `${(object as any).dggid ?? object}`}
                        >
                            <Map mapStyle={BASEMAP_STYLE} reuseMaps />
                        </DeckGL>
                    </div>

                    {/* Floating Title */}
                    <div className="map-overlay workbench-title">
                        <div className="overlay-brand">
                            <img src="/logo.svg" alt="TerraCube IDEAS logo" />
                            <span>TerraCube IDEAS</span>
                        </div>
                        <div>DGGS Analyst Engine</div>
                        <div>Layers: {layers.length} | Visible: {layers.filter((l: LayerConfig) => l.visible).length}</div>
                    </div>
                </main>
            </div>
        </div>
    );
}
