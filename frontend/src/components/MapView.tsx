import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer, GeoJsonLayer, SolidPolygonLayer } from '@deck.gl/layers';
import { _GlobeView as GlobeView, WebMercatorViewport, type Layer, type MapViewState, type Color } from '@deck.gl/core';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { fetchCellsByDggids, getChildren, getNeighbors, getParent } from '../lib/api';
import { getZoneLevel, listZoneIdsForExtent, resolveZonePolygons, type GeoExtent } from '../lib/dggal';

// Free basemap style - no API key required
const BASEMAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

type CellRecord = {
  dggid: string;
  tid: number;
  attr_key: string;
  value_text?: string | null;
  value_num?: number | null;
  value_json?: unknown | null;
};

type PolygonRecord = {
  polygon: number[][];
  cell: CellRecord;
};

type SelectionPolygon = {
  polygon: number[][];
  role: 'selected' | 'neighbor';
};

type MapStats = {
  level?: number;
  zoneCount: number;
  cellCount: number;
  status?: string;
};

type LevelClamp = {
  min?: number;
  max?: number;
};

type MapViewProps = {
  datasetId?: string | null;
  attributeKey?: string | null;
  tid?: number;
  mode: 'viewport' | 'operation';
  overrideCells?: CellRecord[];
  levelClamp?: LevelClamp;
  levelOverride?: number | null;
  relativeDepth?: number;
  useGlobe?: boolean;
  onStats?: (stats: MapStats) => void;
  onCoordinatesChange?: (coords: { lat: number; lng: number } | null) => void;
  onZoomChange?: (zoom: number) => void;
};

const toColor = (value?: number | null): Color => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return [243, 195, 79, 140] as Color;
  }
  const clamped = Math.max(0, Math.min(1, (value + 10) / 20));
  const r = 30 + Math.round(160 * clamped);
  const g = 80 + Math.round(120 * (1 - clamped));
  const b = 110 + Math.round(60 * (1 - clamped));
  return [r, g, b, 170] as Color;
};

const clampLat = (lat: number) => Math.max(-85, Math.min(85, lat));

const buildExtent = (viewState: MapViewState, width: number, height: number): GeoExtent => {
  const viewport = new WebMercatorViewport({
    width,
    height,
    longitude: viewState.longitude ?? 0,
    latitude: viewState.latitude ?? 0,
    zoom: viewState.zoom ?? 1,
  });
  const [minLon, minLat, maxLon, maxLat] = viewport.getBounds();
  return {
    ll: { lat: clampLat(minLat), lon: minLon },
    ur: { lat: clampLat(maxLat), lon: maxLon },
  };
};

const MapView = ({
  datasetId,
  attributeKey,
  tid = 0,
  mode,
  overrideCells = [],
  levelClamp,
  levelOverride,
  relativeDepth,
  useGlobe = false,
  onStats,
  onCoordinatesChange,
  onZoomChange,
}: MapViewProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const [viewState, setViewState] = useState<MapViewState>({
    longitude: 0,
    latitude: 20,
    zoom: 1.5,
    pitch: useGlobe ? 0 : 0,
    bearing: 0,
  });
  const [viewportCells, setViewportCells] = useState<CellRecord[]>([]);
  const [polygons, setPolygons] = useState<PolygonRecord[]>([]);
  const requestId = useRef(0);
  const debounceId = useRef<number | null>(null);
  const fetchAbort = useRef<AbortController | null>(null);
  const polygonAbort = useRef<AbortController | null>(null);
  const lastViewportKey = useRef<string>('');
  const selectionRequestId = useRef(0);
  const [selectedCell, setSelectedCell] = useState<CellRecord | null>(null);
  const [selectionInfo, setSelectionInfo] = useState<{
    level?: number | null;
    parent?: string | null;
    neighbors?: string[];
    children?: string[];
    status?: string;
  } | null>(null);
  const [selectionPolygons, setSelectionPolygons] = useState<SelectionPolygon[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Report zoom changes
  useEffect(() => {
    onZoomChange?.(viewState.zoom ?? 1);
  }, [viewState.zoom, onZoomChange]);

  useEffect(() => {
    if (mode === 'viewport' && (!datasetId || !attributeKey)) {
      setViewportCells([]);
      onStats?.({ zoneCount: 0, cellCount: 0, status: 'Select dataset + attribute key.' });
    }
  }, [attributeKey, datasetId, mode, onStats]);

  useEffect(() => {
    setSelectedCell(null);
    setSelectionInfo(null);
    setSelectionPolygons([]);
  }, [attributeKey, datasetId, mode]);

  const updateViewport = useCallback(async () => {
    if (!datasetId || !attributeKey || mode !== 'viewport') {
      return;
    }
    if (size.width <= 0 || size.height <= 0) {
      return;
    }

    const currentRequest = ++requestId.current;
    onStats?.({ zoneCount: 0, cellCount: 0, status: 'Resolving viewport...' });

    const extent = buildExtent(viewState, size.width, size.height);
    const extentKey = [
      extent.ll.lat.toFixed(4),
      extent.ll.lon.toFixed(4),
      extent.ur.lat.toFixed(4),
      extent.ur.lon.toFixed(4),
      levelOverride ?? 'auto',
      relativeDepth ?? 0,
      datasetId,
      attributeKey,
      tid,
    ].join('|');
    if (extentKey === lastViewportKey.current) {
      return;
    }
    lastViewportKey.current = extentKey;

    const { level, zoneIds } = await listZoneIdsForExtent(extent, size.width, size.height, {
      maxZones: 2600,
      minLevel: levelClamp?.min,
      maxLevel: levelClamp?.max,
      levelOverride: levelOverride ?? undefined,
      relativeDepth,
    });

    if (!zoneIds.length) {
      setViewportCells([]);
      onStats?.({ level, zoneCount: 0, cellCount: 0, status: 'No zones in view.' });
      return;
    }

    onStats?.({ level, zoneCount: zoneIds.length, cellCount: 0, status: 'Fetching cells...' });
    fetchAbort.current?.abort();
    const controller = new AbortController();
    fetchAbort.current = controller;
    let result;
    try {
      result = await fetchCellsByDggids(datasetId, zoneIds, attributeKey, tid, {
        signal: controller.signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      throw err;
    }

    if (currentRequest !== requestId.current) {
      return;
    }

    const cells = result.cells ?? [];
    setViewportCells(cells);
    onStats?.({ level, zoneCount: zoneIds.length, cellCount: cells.length, status: 'Ready' });
  }, [
    attributeKey,
    datasetId,
    levelClamp?.max,
    levelClamp?.min,
    levelOverride,
    mode,
    onStats,
    relativeDepth,
    size.height,
    size.width,
    tid,
    viewState,
  ]);

  useEffect(() => {
    if (mode !== 'viewport') {
      return;
    }
    if (debounceId.current) {
      window.clearTimeout(debounceId.current);
    }
    debounceId.current = window.setTimeout(() => {
      updateViewport().catch((err) => {
        onStats?.({ zoneCount: 0, cellCount: 0, status: err instanceof Error ? err.message : 'Error' });
      });
    }, 350);

    return () => {
      if (debounceId.current) {
        window.clearTimeout(debounceId.current);
      }
    };
  }, [updateViewport, mode]);

  const activeCells = mode === 'operation' ? overrideCells : viewportCells;

  useEffect(() => {
    polygonAbort.current?.abort();
    const controller = new AbortController();
    polygonAbort.current = controller;

    const build = async () => {
      const polygonMap = await resolveZonePolygons(
        activeCells.map((cell) => cell.dggid),
        3,
        { concurrency: 16, signal: controller.signal }
      );
      if (controller.signal.aborted) {
        return;
      }
      const output = activeCells.flatMap((cell) => {
        const polygon = polygonMap.get(cell.dggid);
        return polygon ? [{ polygon, cell }] : [];
      });
      setPolygons(output);
    };

    build().catch((err) => {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
    });

    return () => controller.abort();
  }, [activeCells]);

  const handleSelection = useCallback(async (info: { object?: PolygonRecord | null }) => {
    const record = info.object ?? null;
    if (!record) {
      setSelectedCell(null);
      setSelectionInfo(null);
      setSelectionPolygons([]);
      return;
    }

    const request = ++selectionRequestId.current;
    setSelectedCell(record.cell);
    setSelectionInfo({ status: 'Loading topology...' });
    setSelectionPolygons([]);

    try {
      const [level, neighborsResult, parentResult, childrenResult] = await Promise.all([
        getZoneLevel(record.cell.dggid),
        getNeighbors(record.cell.dggid),
        getParent(record.cell.dggid),
        getChildren(record.cell.dggid),
      ]);

      if (request !== selectionRequestId.current) {
        return;
      }

      const neighbors = neighborsResult.neighbors ?? [];
      const parent = parentResult.parent ?? null;
      const children = childrenResult.children ?? [];

      setSelectionInfo({
        level,
        neighbors,
        parent,
        children,
        status: 'Ready',
      });

      const selectionIds = [record.cell.dggid, ...neighbors];
      const selectionMap = await resolveZonePolygons(selectionIds, 3, { concurrency: 8 });
      if (request !== selectionRequestId.current) {
        return;
      }

      const selectionData: SelectionPolygon[] = [];
      const selectedPolygon = selectionMap.get(record.cell.dggid);
      if (selectedPolygon) {
        selectionData.push({ polygon: selectedPolygon, role: 'selected' });
      }
      neighbors.forEach((neighbor: string) => {
        const polygon = selectionMap.get(neighbor);
        if (polygon) {
          selectionData.push({ polygon, role: 'neighbor' });
        }
      });
      setSelectionPolygons(selectionData);
    } catch (err) {
      if (request === selectionRequestId.current) {
        setSelectionInfo({
          status: err instanceof Error ? err.message : 'Failed to load topology',
        });
      }
    }
  }, []);

  // Handle mouse move for coordinate display
  const handleHover = useCallback((info: { coordinate?: number[] }) => {
    if (info.coordinate && info.coordinate.length >= 2) {
      onCoordinatesChange?.({ lng: info.coordinate[0], lat: info.coordinate[1] });
    } else {
      onCoordinatesChange?.(null);
    }
  }, [onCoordinatesChange]);

  const layers = useMemo<Layer[]>(() => {
    const layerList: Layer[] = [
      new PolygonLayer<PolygonRecord>({
        id: 'dggs-polygons',
        data: polygons,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => toColor(d.cell.value_num ?? null),
        getLineColor: [255, 255, 255, 120],
        lineWidthMinPixels: 1,
        pickable: true,
        autoHighlight: true,
      }),
    ];

    if (selectionPolygons.length) {
      layerList.push(
        new PolygonLayer<SelectionPolygon>({
          id: 'selection-ring',
          data: selectionPolygons,
          getPolygon: (d) => d.polygon,
          getFillColor: (d) => (d.role === 'selected' ? [255, 184, 77, 130] : [91, 200, 255, 80]),
          getLineColor: (d) => (d.role === 'selected' ? [255, 160, 40, 200] : [91, 200, 255, 140]),
          lineWidthMinPixels: 2,
          pickable: false,
        })
      );
    }

    return layerList;
  }, [polygons, selectionPolygons]);

  // Globe view configuration
  const views = useMemo(() => {
    if (useGlobe) {
      return new GlobeView({ id: 'globe', resolution: 10 });
    }
    return undefined;
  }, [useGlobe]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      <DeckGL
        layers={layers}
        viewState={viewState}
        views={views}
        onViewStateChange={({ viewState: nextState }) => {
          if ('longitude' in nextState && 'latitude' in nextState && 'zoom' in nextState) {
            setViewState(nextState as MapViewState);
          }
        }}
        controller
        onClick={handleSelection}
        onHover={handleHover}
        getTooltip={({ object }) =>
          object
            ? {
              text: `${object.cell.dggid}\n${object.cell.attr_key}\n${object.cell.value_num ?? object.cell.value_text ?? ''}`,
            }
            : null
        }
      >
        {!useGlobe && (
          <Map
            mapStyle={BASEMAP_STYLE}
            reuseMaps
          />
        )}
      </DeckGL>
      {selectedCell && selectionInfo && (
        <div className="map-inspector">
          <div className="map-inspector__title">Cell Inspector</div>
          <div className="map-inspector__row">
            <span>DGGID</span>
            <strong>{selectedCell.dggid}</strong>
          </div>
          <div className="map-inspector__row">
            <span>Attribute</span>
            <strong>{selectedCell.attr_key}</strong>
          </div>
          <div className="map-inspector__row">
            <span>Value</span>
            <strong>{selectedCell.value_num ?? selectedCell.value_text ?? '—'}</strong>
          </div>
          <div className="map-inspector__row">
            <span>Level</span>
            <strong>{selectionInfo.level ?? '—'}</strong>
          </div>
          <div className="map-inspector__row">
            <span>Parent</span>
            <strong>{selectionInfo.parent ?? '—'}</strong>
          </div>
          <div className="map-inspector__row">
            <span>Neighbors</span>
            <strong>{selectionInfo.neighbors?.length ?? 0}</strong>
          </div>
          <div className="map-inspector__row">
            <span>Children</span>
            <strong>{selectionInfo.children?.length ?? 0}</strong>
          </div>
          {selectionInfo.status && <div className="map-inspector__status">{selectionInfo.status}</div>}
        </div>
      )}
    </div>
  );
};

export default MapView;
