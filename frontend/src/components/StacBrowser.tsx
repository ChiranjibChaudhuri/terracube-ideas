import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../lib/api';

type StacCatalog = {
  id: string;
  name: string;
  api_url: string;
  catalog_type: string;
  auth_type: string | null;
  collections: string[];
};

type StacScene = {
  stac_item_id: string;
  collection: string;
  bbox: number[] | null;
  datetime: string | null;
  cloud_cover: number | null;
  bands: Record<string, { href: string; type: string }>;
  thumbnail_url: string | null;
  properties: Record<string, unknown>;
};

type StacCollectionRecord = {
  id: string;
  name: string;
  stac_collection: string;
  bbox: number[] | null;
  date_start: string | null;
  date_end: string | null;
  scene_count: number;
  status: string;
  error: string | null;
  created_at: string | null;
};

type StacCollectionDetail = StacCollectionRecord & {
  available_bands: string[];
  scenes: Array<{
    id: string;
    stac_item_id: string;
    datetime: string | null;
    cloud_cover: number | null;
    bbox: number[] | null;
    bands: string[];
    thumbnail_url: string | null;
    dggs_cell_count: number;
    ingested: boolean;
    dataset_id: string | null;
  }>;
};

interface StacBrowserProps {
  currentViewportBbox?: [number, number, number, number] | null;
  onIngestComplete?: (datasetId: string) => void;
}

export const StacBrowser: React.FC<StacBrowserProps> = ({
  currentViewportBbox,
  onIngestComplete,
}) => {
  const [view, setView] = useState<'search' | 'collections'>('search');
  const [catalogs, setCatalogs] = useState<StacCatalog[]>([]);
  const [selectedCatalog, setSelectedCatalog] = useState<string>('');
  const [selectedStacCollection, setSelectedStacCollection] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Search parameters
  const [bboxW, setBboxW] = useState('');
  const [bboxS, setBboxS] = useState('');
  const [bboxE, setBboxE] = useState('');
  const [bboxN, setBboxN] = useState('');
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [cloudCover, setCloudCover] = useState('30');
  const [maxItems, setMaxItems] = useState('25');

  // Search results
  const [searchResults, setSearchResults] = useState<StacScene[]>([]);
  const [availableBands, setAvailableBands] = useState<string[]>([]);

  // Collection creation
  const [collectionName, setCollectionName] = useState('');
  const [indexingStatus, setIndexingStatus] = useState('');

  // Collections list
  const [collections, setCollections] = useState<StacCollectionRecord[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<StacCollectionDetail | null>(null);

  // Ingestion
  const [selectedScenes, setSelectedScenes] = useState<Set<string>>(new Set());
  const [selectedBands, setSelectedBands] = useState<Set<string>>(new Set());
  const [targetLevel, setTargetLevel] = useState(9);
  const [ingestName, setIngestName] = useState('');
  const [ingestStatus, setIngestStatus] = useState('');

  // Load catalogs on mount
  useEffect(() => {
    apiFetch('/api/stac/catalogs')
      .then((data) => {
        setCatalogs(data);
        if (data.length > 0) {
          setSelectedCatalog(data[0].id);
          if (data[0].collections.length > 0) {
            setSelectedStacCollection(data[0].collections[0]);
          }
        }
      })
      .catch(() => setError('Failed to load STAC catalogs'));
  }, []);

  // Update available collections when catalog changes
  const currentCatalog = catalogs.find((c) => c.id === selectedCatalog);
  const catalogCollections = currentCatalog?.collections || [];

  useEffect(() => {
    if (catalogCollections.length > 0 && !catalogCollections.includes(selectedStacCollection)) {
      setSelectedStacCollection(catalogCollections[0]);
    }
  }, [selectedCatalog, catalogCollections, selectedStacCollection]);

  const applyCurrentViewport = useCallback(() => {
    if (!currentViewportBbox) return;

    const [west, south, east, north] = currentViewportBbox;
    setBboxW(west.toFixed(4));
    setBboxS(south.toFixed(4));
    setBboxE(east.toFixed(4));
    setBboxN(north.toFixed(4));
  }, [currentViewportBbox]);

  // Search STAC
  const handleSearch = useCallback(async () => {
    if (!selectedCatalog || !selectedStacCollection) return;

    setLoading(true);
    setError('');
    setSearchResults([]);

    const bbox =
      bboxW && bboxS && bboxE && bboxN
        ? [parseFloat(bboxW), parseFloat(bboxS), parseFloat(bboxE), parseFloat(bboxN)]
        : undefined;

    try {
      const result = await apiFetch(`/api/stac/catalogs/${selectedCatalog}/search`, {
        method: 'POST',
        body: JSON.stringify({
          collection: selectedStacCollection,
          bbox,
          date_start: dateStart || undefined,
          date_end: dateEnd || undefined,
          cloud_cover_lt: cloudCover ? parseFloat(cloudCover) : undefined,
          max_items: parseInt(maxItems) || 25,
        }),
      });
      setSearchResults(result.scenes || []);
      setAvailableBands(result.available_bands || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }, [selectedCatalog, selectedStacCollection, bboxW, bboxS, bboxE, bboxN, dateStart, dateEnd, cloudCover, maxItems]);

  // Create indexed collection
  const handleCreateCollection = useCallback(async () => {
    if (!selectedCatalog || !selectedStacCollection || !collectionName) return;

    setIndexingStatus('Creating collection...');
    setError('');

    const bbox =
      bboxW && bboxS && bboxE && bboxN
        ? [parseFloat(bboxW), parseFloat(bboxS), parseFloat(bboxE), parseFloat(bboxN)]
        : undefined;

    try {
      const result = await apiFetch('/api/stac/collections', {
        method: 'POST',
        body: JSON.stringify({
          catalog_id: selectedCatalog,
          stac_collection: selectedStacCollection,
          name: collectionName,
          bbox,
          date_start: dateStart || undefined,
          date_end: dateEnd || undefined,
          cloud_cover_lt: cloudCover ? parseFloat(cloudCover) : undefined,
          max_items: parseInt(maxItems) || 25,
        }),
      });
      setIndexingStatus(
        result.status === 'ready'
          ? `Collection ready: ${result.scene_count} scenes indexed`
          : `Status: ${result.status}`
      );
      // Refresh collections list
      loadCollections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Collection creation failed');
      setIndexingStatus('');
    }
  }, [selectedCatalog, selectedStacCollection, collectionName, bboxW, bboxS, bboxE, bboxN, dateStart, dateEnd, cloudCover, maxItems]);

  // Load user collections
  const loadCollections = useCallback(async () => {
    try {
      const data = await apiFetch('/api/stac/collections');
      setCollections(data);
    } catch {
      // Silently fail
    }
  }, []);

  useEffect(() => {
    if (view === 'collections') loadCollections();
  }, [view, loadCollections]);

  // Load collection detail
  const loadCollectionDetail = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const data = await apiFetch(`/api/stac/collections/${id}`);
      setSelectedCollection(data);
      setSelectedScenes(new Set());
      setSelectedBands(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load collection');
    } finally {
      setLoading(false);
    }
  }, []);

  // Toggle scene selection
  const toggleScene = (sceneId: string) => {
    setSelectedScenes((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) next.delete(sceneId);
      else next.add(sceneId);
      return next;
    });
  };

  // Toggle band selection
  const toggleBand = (band: string) => {
    setSelectedBands((prev) => {
      const next = new Set(prev);
      if (next.has(band)) next.delete(band);
      else next.add(band);
      return next;
    });
  };

  // Select all scenes
  const selectAllScenes = () => {
    if (!selectedCollection) return;
    const allIds = new Set(selectedCollection.scenes.map((s) => s.id));
    setSelectedScenes(allIds);
  };

  // Ingest selected scenes
  const handleIngest = useCallback(async () => {
    if (!selectedCollection || selectedScenes.size === 0 || selectedBands.size === 0) return;

    setIngestStatus('Starting ingestion...');
    setError('');

    try {
      const result = await apiFetch(`/api/stac/collections/${selectedCollection.id}/ingest`, {
        method: 'POST',
        body: JSON.stringify({
          scene_ids: Array.from(selectedScenes),
          bands: Array.from(selectedBands),
          target_level: targetLevel,
          dataset_name: ingestName || `${selectedCollection.name} - Level ${targetLevel}`,
        }),
      });
      setIngestStatus(
        `Ingestion started for dataset ${result.dataset_id}. ${result.scene_count} scenes are being processed.`
      );
      if (onIngestComplete && result.dataset_id) {
        onIngestComplete(result.dataset_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingestion failed');
      setIngestStatus('');
    }
  }, [selectedCollection, selectedScenes, selectedBands, targetLevel, ingestName, onIngestComplete]);

  // Delete collection
  const handleDeleteCollection = useCallback(
    async (id: string) => {
      try {
        await apiFetch(`/api/stac/collections/${id}`, { method: 'DELETE' });
        setSelectedCollection(null);
        loadCollections();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Delete failed');
      }
    },
    [loadCollections]
  );

  const formatDate = (iso: string | null) => {
    if (!iso) return '--';
    try {
      return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="stac-browser">
      {/* Tab navigation */}
      <div className="stac-tabs">
        <button className={`stac-tab ${view === 'search' ? 'active' : ''}`} onClick={() => setView('search')}>
          Search
        </button>
        <button className={`stac-tab ${view === 'collections' ? 'active' : ''}`} onClick={() => setView('collections')}>
          Collections
        </button>
      </div>

      {error && <div className="stac-error">{error}</div>}

      {/* ── SEARCH VIEW ────────────────────────────── */}
      {view === 'search' && (
        <div className="stac-search-panel">
          {/* Catalog & Collection */}
          <div className="stac-form-group">
            <label>Catalog</label>
            <select value={selectedCatalog} onChange={(e) => setSelectedCatalog(e.target.value)}>
              {catalogs.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="stac-form-group">
            <label>Dataset</label>
            <select value={selectedStacCollection} onChange={(e) => setSelectedStacCollection(e.target.value)}>
              {catalogCollections.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {/* Bbox */}
          <div className="stac-form-group">
            <div className="stac-form-label-row">
              <label>Bounding Box (W, S, E, N)</label>
              <button
                type="button"
                className="stac-link-btn"
                onClick={applyCurrentViewport}
                disabled={!currentViewportBbox}
              >
                Use Current View
              </button>
            </div>
            <div className="stac-bbox-row">
              <input placeholder="W" value={bboxW} onChange={(e) => setBboxW(e.target.value)} />
              <input placeholder="S" value={bboxS} onChange={(e) => setBboxS(e.target.value)} />
              <input placeholder="E" value={bboxE} onChange={(e) => setBboxE(e.target.value)} />
              <input placeholder="N" value={bboxN} onChange={(e) => setBboxN(e.target.value)} />
            </div>
            <span className="stac-bbox-hint">
              {currentViewportBbox ? 'Map viewport is available as the search AOI.' : 'Pan or zoom the map to enable viewport AOI.'}
            </span>
          </div>

          {/* Date range */}
          <div className="stac-form-row">
            <div className="stac-form-group">
              <label>Start Date</label>
              <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)} />
            </div>
            <div className="stac-form-group">
              <label>End Date</label>
              <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)} />
            </div>
          </div>

          {/* Cloud cover & max items */}
          <div className="stac-form-row">
            <div className="stac-form-group">
              <label>Cloud Cover &lt;</label>
              <input type="number" min="0" max="100" value={cloudCover} onChange={(e) => setCloudCover(e.target.value)} />
            </div>
            <div className="stac-form-group">
              <label>Max Results</label>
              <input type="number" min="1" max="500" value={maxItems} onChange={(e) => setMaxItems(e.target.value)} />
            </div>
          </div>

          <button className="button-primary stac-search-btn" onClick={handleSearch} disabled={loading}>
            {loading ? 'Searching...' : 'Search STAC'}
          </button>

          {/* Search results */}
          {searchResults.length > 0 && (
            <div className="stac-results">
              <div className="stac-results-header">
                <strong>{searchResults.length} scenes found</strong>
                {availableBands.length > 0 && (
                  <span className="stac-band-count">{availableBands.length} bands available</span>
                )}
              </div>

              <div className="stac-scene-list">
                {searchResults.map((scene) => (
                  <div key={scene.stac_item_id} className="stac-scene-card">
                    {scene.thumbnail_url && (
                      <img src={scene.thumbnail_url} alt="" className="stac-thumbnail" loading="lazy" />
                    )}
                    <div className="stac-scene-info">
                      <strong>{scene.stac_item_id}</strong>
                      <span>{formatDate(scene.datetime)}</span>
                      {scene.cloud_cover != null && (
                        <span className="stac-cloud">{scene.cloud_cover.toFixed(1)}% cloud</span>
                      )}
                      <span className="stac-bands">{Object.keys(scene.bands).length} bands</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Create Collection */}
              <div className="stac-create-collection">
                <label>Collection Name</label>
                <input
                  type="text"
                  placeholder="My Sentinel-2 collection"
                  value={collectionName}
                  onChange={(e) => setCollectionName(e.target.value)}
                />
                <button
                  className="button-primary"
                  onClick={handleCreateCollection}
                  disabled={!collectionName || loading}
                >
                  Index Collection ({searchResults.length} scenes)
                </button>
                {indexingStatus && <div className="stac-status">{indexingStatus}</div>}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── COLLECTIONS VIEW ──────────────────────── */}
      {view === 'collections' && !selectedCollection && (
        <div className="stac-collections-list">
          {collections.length === 0 && <p className="stac-empty">No collections yet. Search and index scenes first.</p>}
          {collections.map((col) => (
            <div key={col.id} className="stac-collection-card" onClick={() => loadCollectionDetail(col.id)}>
              <div className="stac-collection-header">
                <strong>{col.name}</strong>
                <span className={`stac-badge stac-badge-${col.status}`}>{col.status}</span>
              </div>
              <div className="stac-collection-meta">
                <span>{col.stac_collection}</span>
                <span>{col.scene_count} scenes</span>
                {col.date_start && <span>{col.date_start} &rarr; {col.date_end}</span>}
              </div>
              {col.error && <div className="stac-error-inline">{col.error}</div>}
            </div>
          ))}
        </div>
      )}

      {/* ── COLLECTION DETAIL VIEW ───────────────── */}
      {view === 'collections' && selectedCollection && (
        <div className="stac-collection-detail">
          <button className="stac-back-btn" onClick={() => setSelectedCollection(null)}>
            &larr; Back to collections
          </button>

          <div className="stac-detail-header">
            <h3>{selectedCollection.name}</h3>
            <span className={`stac-badge stac-badge-${selectedCollection.status}`}>{selectedCollection.status}</span>
          </div>

          <div className="stac-detail-meta">
            <span>{selectedCollection.stac_collection}</span>
            <span>{selectedCollection.scenes.length} scenes</span>
          </div>

          {/* Scene list with checkboxes */}
          <div className="stac-scene-select-header">
            <button className="stac-link-btn" onClick={selectAllScenes}>
              Select All
            </button>
            <button className="stac-link-btn" onClick={() => setSelectedScenes(new Set())}>
              Clear
            </button>
            <span>{selectedScenes.size} selected</span>
          </div>

          <div className="stac-scene-list">
            {selectedCollection.scenes.map((scene) => (
              <div
                key={scene.id}
                className={`stac-scene-card selectable ${selectedScenes.has(scene.id) ? 'selected' : ''}`}
                onClick={() => toggleScene(scene.id)}
              >
                {scene.thumbnail_url && (
                  <img src={scene.thumbnail_url} alt="" className="stac-thumbnail" loading="lazy" />
                )}
                <div className="stac-scene-info">
                  <strong>{scene.stac_item_id}</strong>
                  <span>{formatDate(scene.datetime)}</span>
                  {scene.cloud_cover != null && (
                    <span className="stac-cloud">{scene.cloud_cover.toFixed(1)}% cloud</span>
                  )}
                  <span>{scene.dggs_cell_count} DGGS cells</span>
                  {scene.ingested && <span className="stac-badge stac-badge-ready">Ingested</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Band selection */}
          {selectedCollection.scenes.length > 0 && (
            <div className="stac-band-select">
              <label>Select Bands</label>
              <div className="stac-band-chips">
                {(selectedCollection.available_bands || []).map((band) => (
                  <button
                    key={band}
                    className={`stac-chip ${selectedBands.has(band) ? 'active' : ''}`}
                    onClick={() => toggleBand(band)}
                  >
                    {band}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Ingest controls */}
          <div className="stac-ingest-controls">
            <div className="stac-form-group">
              <label>DGGS Level</label>
              <input
                type="range"
                min="1"
                max="12"
                value={targetLevel}
                onChange={(e) => setTargetLevel(parseInt(e.target.value))}
              />
              <span className="stac-level-value">Level {targetLevel}</span>
            </div>

            <div className="stac-form-group">
              <label>Dataset Name</label>
              <input
                type="text"
                placeholder={`${selectedCollection.name} - Level ${targetLevel}`}
                value={ingestName}
                onChange={(e) => setIngestName(e.target.value)}
              />
            </div>

            <button
              className="button-primary stac-ingest-btn"
              onClick={handleIngest}
              disabled={selectedScenes.size === 0 || selectedBands.size === 0}
            >
              Ingest {selectedScenes.size} scenes &times; {selectedBands.size} bands
            </button>

            {ingestStatus && <div className="stac-status">{ingestStatus}</div>}
          </div>

          <button className="stac-delete-btn" onClick={() => handleDeleteCollection(selectedCollection.id)}>
            Delete Collection
          </button>
        </div>
      )}
    </div>
  );
};
