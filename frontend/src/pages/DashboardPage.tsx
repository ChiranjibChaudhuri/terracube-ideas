import { useEffect, useState, useCallback } from 'react';
import MapView from '../components/MapView';
import { DatasetSearch } from '../components/DatasetSearch';
import { LayerList } from '../components/LayerList';
import { ToolboxPanel } from '../components/ToolboxPanel';
import { MapInfoBar } from '../components/MapInfoBar';
import { ScaleBar } from '../components/ScaleBar';
import { ColorLegend } from '../components/ColorLegend';
import { logout } from '../lib/api';
import { useAppStore, type LayerConfig } from '../lib/store';
import { fetchCells } from '../lib/api';

type Dataset = {
  id: string;
  name: string;
  description?: string;
  dggs_name?: string;
  level?: number;
  status?: string;
  metadata?: Record<string, any>;
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
  const { layers, addLayer } = useAppStore();
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [mapMode, setMapMode] = useState<'viewport' | 'operation'>('viewport');
  const [mapStats, setMapStats] = useState<MapStats>({ zoneCount: 0, cellCount: 0 });
  const [status, setStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [renderKey, setRenderKey] = useState('');
  const [renderTid, setRenderTid] = useState('0');
  const [levelMode, setLevelMode] = useState<'auto' | 'fixed'>('auto');
  const [fixedLevel, setFixedLevel] = useState(3);

  const [operationCells, setOperationCells] = useState<CellRecord[]>([]);

  // Scientific UI state
  const [coordinates, setCoordinates] = useState<{ lat: number; lng: number } | null>(null);
  const [zoom, setZoom] = useState(1.5);
  const [useGlobe, setUseGlobe] = useState(false);

  // Collapsible sections state
  const [sectionsOpen, setSectionsOpen] = useState({
    layers: true,
    toolbox: true,
    settings: false
  });

  const levelMin = Number(selectedDataset?.metadata?.min_level ?? 0);
  const levelMax = Number(selectedDataset?.metadata?.max_level ?? 12);
  const clampedLevelMin = Number.isFinite(levelMin) ? levelMin : 0;
  const clampedLevelMax = Number.isFinite(levelMax) ? levelMax : 12;

  const toggleSection = (section: keyof typeof sectionsOpen) => {
    setSectionsOpen(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Handle dataset search selection
  const handleDatasetSelect = useCallback(async (dataset: Dataset) => {
    setStatus('Loading dataset...');
    setIsLoading(true);
    try {
      // Fetch cells from the dataset
      const result = await fetchCells(dataset.id, {
        key: dataset.metadata?.attr_key,
        limit: '2000'
      });
      const cells = result.cells ?? [];

      if (cells.length > 0) {
        const dggids = cells.map((c: CellRecord) => c.dggid);
        addLayer({
          id: `layer-${dataset.id}-${Date.now()}`,
          name: dataset.name,
          type: 'dggs',
          data: dggids,
          visible: true,
          opacity: 0.6,
          color: [31, 138, 138] // Sea-500 from our palette
        });
        setStatus(`Loaded ${cells.length} cells from ${dataset.name}`);
      } else {
        setStatus('No cells found in dataset');
      }
      setSelectedDataset(dataset);
      setRenderKey(dataset.metadata?.attr_key ?? '');
      if (dataset.metadata?.min_level) {
        setFixedLevel(dataset.metadata.min_level);
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Failed to load dataset');
    } finally {
      setIsLoading(false);
    }
  }, [addLayer]);

  return (
    <div className="page dashboard">
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
              mode={mapMode}
              overrideCells={operationCells}
              levelClamp={{
                min: selectedDataset?.metadata?.min_level,
                max: selectedDataset?.metadata?.max_level,
              }}
              levelOverride={levelMode === 'fixed' ? fixedLevel : null}
              onStats={setMapStats}
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
                  min={-10}
                  max={10}
                  unit=""
                  colorRamp="viridis"
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
