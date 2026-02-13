import { useEffect, useState, useCallback } from 'react';
import MapView from '../components/MapView';
import { DatasetSearch } from '../components/DatasetSearch';
import { LayerList } from '../components/LayerList';
import { ToolboxPanel } from '../components/ToolboxPanel';
import { MapInfoBar } from '../components/MapInfoBar';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/Toast';
import { ScaleBar } from '../components/ScaleBar';
import { ColorLegend } from '../components/ColorLegend';
import { logout } from '../lib/api';
import { useAppStore, type LayerConfig } from '../lib/store';
import { getDatasetMetadata, isOperationResultDataset } from '../lib/datasetUtils';
import { BASEMAPS, DEFAULT_BASEMAP_ID } from '../lib/basemaps';
import { fetchCells } from '../lib/api';

type Dataset = {
  id: string;
  name: string;
  description?: string;
  dggs_name?: string;
  level?: number;
  status?: string;
  metadata?: Record<string, any> | string | null;
};

type CellRecord = {
  dggid: string;
  tid: number;
  attr_key: string;
  value_text?: string | null;
  value_num?: number | null;
  value_json?: unknown | null;
};

type MapStats = {
  level?: number;
  zoneCount: number;
  cellCount: number;
  status?: string;
};

const DashboardPage = () => {
  const { layers, addLayer, updateLayer } = useAppStore();
  const { messages } = useToast();
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [mapMode, setMapMode] = useState<'viewport' | 'operation'>('viewport');
  const [mapStats, setMapStats] = useState<MapStats>({ zoneCount: 0, cellCount: 0 });
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [renderKey, setRenderKey] = useState('');
  const [renderTid, setRenderTid] = useState('0');
  const [levelMode, setLevelMode] = useState<'auto' | 'fixed'>('auto');
  const [fixedLevel, setFixedLevel] = useState(3);
  const [levelOffset, setLevelOffset] = useState(3);

  const [operationCells, setOperationCells] = useState<CellRecord[]>([]);

  // Scientific UI state
  const [coordinates, setCoordinates] = useState<{ lat: number; lng: number } | null>(null);
  const [zoom, setZoom] = useState(1.5);
  const [useGlobe, setUseGlobe] = useState(false);
  const [basemapId, setBasemapId] = useState(DEFAULT_BASEMAP_ID);

  // Collapsible sections state
  const [sectionsOpen, setSectionsOpen] = useState({
    layers: true,
    toolbox: true,
    team: false,
    billing: false,
    settings: false
  });

  const activeLayer = selectedDataset
    ? [...layers].reverse().find((layer) => layer.datasetId === selectedDataset.id)
    : null;

  const selectedMetadata: Record<string, any> = selectedDataset ? getDatasetMetadata(selectedDataset) : {};
  const levelMin = Number(selectedMetadata.min_level ?? 0);
  const levelMax = Number(selectedMetadata.max_level ?? 15);
  const clampedLevelMin = Number.isFinite(levelMin) ? levelMin : 0;
  const clampedLevelMax = Number.isFinite(levelMax) ? levelMax : 15;
  const basemap = BASEMAPS.find((bm) => bm.id === basemapId) ?? BASEMAPS[0];

  const toggleSection = (section: keyof typeof sectionsOpen) => {
    setSectionsOpen(prev => ({ ...prev, [section]: !prev[section] }));
  };
  // Handle dataset search selection
  const handleDatasetSelect = useCallback(async (dataset: Dataset) => {
    setStatus('Loading dataset...');
    setIsLoading(true);
    try {
      const isOperationResult = isOperationResultDataset(dataset);
      // Don't pre-fetch cells - let MapView load dynamically based on viewport
      // (except for a tiny sample when attr_key is missing)
      const metadata = getDatasetMetadata(dataset);
      let attrKey = metadata.attr_key;
      if (!attrKey) {
        try {
          const sample = await fetchCells(dataset.id, { limit: '1' });
          const sampleKey = sample?.cells?.[0]?.attr_key;
          if (sampleKey) {
            attrKey = sampleKey;
          }
        } catch {
          // Ignore lookup errors; MapView will surface missing attr key
        }
      }
      addLayer({
        id: `layer-${dataset.id}-${Date.now()}`,
        name: dataset.name,
        type: 'dggs',
        data: [],  // Empty - MapView will load based on viewport
        visible: true,
        opacity: 0.6,
        origin: isOperationResult ? 'operation' : 'dataset',
        datasetId: dataset.id,
        attrKey,
        dggsName: dataset.dggs_name,
        minValue: metadata.min_value,
        maxValue: metadata.max_value,
      });
      setStatus(`Layer "${dataset.name}" added - cells load on viewport`);
      setSelectedDataset(dataset);
      setRenderKey(attrKey ?? '');
      if (metadata.min_level) {
        setFixedLevel(metadata.min_level);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Failed to load dataset');
    } finally {
      setIsLoading(false);
    }
  }, [addLayer]);

  const handleMapStats = useCallback((stats: MapStats) => {
    setMapStats(stats);
    if (activeLayer) {
      updateLayer(activeLayer.id, { cellCount: stats.cellCount });
    }
  }, [activeLayer, updateLayer]);

  return (
    <div className="page dashboard">
      <ToastContainer messages={messages} onRemove={() => {}} />
      <div className="dashboard-shell">
        <aside className="sidebar">
          {/* Header */}
          <div className="sidebar-logo">
            <img src="/logo.svg" alt="TerraCube IDEAS logo" />
            <h3>TerraCube IDEAS</h3>
          </div>

          {/* Dataset Search */}
          <div className="section">
            <div className="section-header" onClick={() => toggleSection('layers')}>
              <span className="section-title">Add Layer</span>
              <span className="section-toggle">{sectionsOpen.layers ? '−' : '+'}</span>
            </div>
            {sectionsOpen.layers && (
              <div className="section-content">
                <DatasetSearch onSelect={handleDatasetSelect} />
                {isLoading && <div className="loading-indicator">Loading...</div>}
                <LayerList />
              </div>
            )}
          </div>

          {/* Toolbox */}
          <div className="section">
            <div className="section-header" onClick={() => toggleSection('toolbox')}>
              <span className="section-title">Toolbox</span>
              <span className="section-toggle">{sectionsOpen.toolbox ? '−' : '+'}</span>
            </div>
            {sectionsOpen.toolbox && (
              <div className="section-content">
                <ToolboxPanel />
              </div>
            )}
          </div>

          {/* Team (collapsed by default) */}
          <div className="section">
            <div className="section-header" onClick={() => toggleSection('team')}>
              <span className="section-title">Team</span>
              <span className="section-toggle">{sectionsOpen.team ? '−' : '+'}</span>
            </div>
            {sectionsOpen.team && (
              <div className="section-content">
                <div className="toolbox">
                  <div className="toolbox-field">
                    <label className="toolbox-label">Invite Teammate</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <input type="email" className="toolbox-input" placeholder="email@example.com" />
                      <button className="button-primary" style={{ padding: '0.5rem 1rem' }} onClick={() => setStatus('Invite sent to teammate!')}>Send</button>
                    </div>
                  </div>
                  <div className="toolbox-field">
                    <label className="toolbox-label">Active Members</label>
                    <div className="badge" style={{ marginBottom: '0.5rem' }}>Demo User (Admin)</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Billing (collapsed by default) */}
          <div className="section">
            <div className="section-header" onClick={() => toggleSection('billing')}>
              <span className="section-title">Billing</span>
              <span className="section-toggle">{sectionsOpen.billing ? '−' : '+'}</span>
            </div>
            {sectionsOpen.billing && (
              <div className="section-content">
                <div className="toolbox">
                  <div className="toolbox-field">
                    <label className="toolbox-label">Current Plan: Professional</label>
                    <p style={{ fontSize: '0.8rem', opacity: 0.8 }}>Next billing date: Feb 28, 2026</p>
                  </div>
                  <button className="button-secondary" style={{ width: '100%' }} onClick={() => setStatus('Redirecting to stripe (Mock)...')}>Manage Subscription</button>
                </div>
              </div>
            )}
          </div>

          {/* Settings (collapsed by default) */}
          <div className="section">
            <div className="section-header" onClick={() => toggleSection('settings')}>
              <span className="section-title">Map Settings</span>
              <span className="section-toggle">{sectionsOpen.settings ? '−' : '+'}</span>
            </div>
            {sectionsOpen.settings && (
              <div className="section-content">
                <div className="toolbox">
                  {/* Globe Toggle */}
                  <div className="toolbox-field">
                    <label className="toolbox-label">
                      <input
                        type="checkbox"
                        checked={useGlobe}
                        onChange={(e) => setUseGlobe(e.target.checked)}
                        style={{ marginRight: '0.5rem' }}
                      />
                      3D Globe View
                    </label>
                  </div>

                  <div className="toolbox-field">
                    <label className="toolbox-label">Basemap</label>
                    <select
                      className="toolbox-select"
                      value={basemapId}
                      onChange={(e) => setBasemapId(e.target.value)}
                    >
                      {BASEMAPS.map((bm) => (
                        <option key={bm.id} value={bm.id}>
                          {bm.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="toolbox-field">
                    <label className="toolbox-label">Resolution Mode</label>
                    <select
                      className="toolbox-select"
                      value={levelMode}
                      onChange={(e) => setLevelMode(e.target.value as 'auto' | 'fixed')}
                    >
                      <option value="auto">Auto (zoom-based)</option>
                      <option value="fixed">Fixed level</option>
                    </select>
                  </div>
                  {levelMode === 'auto' && (
                    <div className="toolbox-field">
                      <label className="toolbox-label">
                        Zoom Offset: {levelOffset >= 0 ? `+${levelOffset}` : levelOffset}
                      </label>
                      <input
                        type="range"
                        min={-3}
                        max={6}
                        step={1}
                        value={levelOffset}
                        onChange={(e) => setLevelOffset(Number(e.target.value))}
                        className="toolbox-range"
                      />
                    </div>
                  )}
                  {levelMode === 'fixed' && (
                    <div className="toolbox-field">
                      <label className="toolbox-label">Level: {fixedLevel}</label>
                      <input
                        type="range"
                        min={clampedLevelMin}
                        max={clampedLevelMax}
                        value={fixedLevel}
                        onChange={(e) => setFixedLevel(Number(e.target.value))}
                        className="toolbox-range"
                      />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="sidebar-footer">
            <div className="sidebar-attribution">
              Powered by <a href="https://github.com/r-barnes/dggal" target="_blank" rel="noopener noreferrer">DGGAL</a>
            </div>
            <button className="button-secondary" onClick={() => { logout(); window.location.href = '/'; }}>
              Sign out
            </button>
          </div>
        </aside>

        <main className="map-panel">
          <div className="map-shell">
            <MapView
              datasetId={selectedDataset?.id}
              attributeKey={renderKey.trim() || null}
              tid={Number(renderTid) || 0}
              dggsName={selectedDataset?.dggs_name ?? null}
              basemapStyle={basemap?.styleUrl}
              globeTexture={basemap?.textureUrl}
              layerStyle={activeLayer ? {
                color: activeLayer.color,
                opacity: activeLayer.opacity,
                visible: activeLayer.visible,
                minValue: activeLayer.minValue ?? selectedMetadata.min_value,
                maxValue: activeLayer.maxValue ?? selectedMetadata.max_value,
                colorRamp: activeLayer.colorRamp,
              } : undefined}
              mode={mapMode}
              overrideCells={operationCells}
              levelClamp={{
                min: selectedMetadata.min_level,
                max: selectedMetadata.max_level,
              }}
              levelOverride={levelMode === 'fixed' ? fixedLevel : null}
              levelOffset={levelOffset}
              onStats={handleMapStats}
              useGlobe={useGlobe}
              onCoordinatesChange={setCoordinates}
              onZoomChange={setZoom}
            />

            {/* Scale Bar */}
            <div className="map-scale-bar">
              <ScaleBar zoom={zoom} latitude={coordinates?.lat ?? 0} />
            </div>

            {/* Color Legend (when layer loaded) */}
            {layers.length > 0 && (
              <div className="map-legend">
                <ColorLegend
                  title={selectedDataset?.name ?? 'Layer'}
                  min={activeLayer?.minValue ?? selectedMetadata.min_value ?? -10}
                  max={activeLayer?.maxValue ?? selectedMetadata.max_value ?? 10}
                  unit={selectedMetadata.attr_key === 'temp_celsius' ? '°C' : ''}
                  colorRamp={activeLayer?.colorRamp ?? "viridis"}
                />
              </div>
            )}
          </div>

          {/* Status Info Bar at bottom */}
          <MapInfoBar
            coordinates={coordinates}
            zoom={zoom}
            level={mapStats.level}
            cellCount={mapStats.cellCount}
            status={status || mapStats.status || 'Ready'}
          />
        </main>
      </div>
    </div>
  );
};

export default DashboardPage;
