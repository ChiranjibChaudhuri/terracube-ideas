import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PolygonLayer, GeoJsonLayer, SolidPolygonLayer, BitmapLayer } from '@deck.gl/layers';
import { _GlobeView as GlobeView, WebMercatorViewport, COORDINATE_SYSTEM, type Layer, type MapViewState, type Color } from '@deck.gl/core';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { scaleSequential } from 'd3-scale';
import {
  interpolateViridis,
  interpolatePlasma,
  interpolateMagma,
  interpolateInferno,
  interpolateWarm,
  interpolateCool,
  interpolateBlues,
  interpolateRdBu,
  interpolateSpectral
} from 'd3-scale-chromatic';
import { rgb } from 'd3-color';
import { fetchCellsByDggids, getChildren, getNeighbors, getParent, listZonesFromBackend } from '../lib/api';
import { getZoneLevel, resolveZonePolygons, type GeoExtent } from '../lib/dggal';

// Default basemap style - no API key required
const BASEMAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

// Default earth texture for globe view (bright version)
const EARTH_TEXTURE_URL = 'https://unpkg.com/three-globe@2.26.0/example/img/earth-blue-marble.jpg';

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

type LayerStyle = {
  color?: [number, number, number];
  opacity?: number;
  visible?: boolean;
  minValue?: number;
  maxValue?: number;
  colorRamp?: string;
};

type MapViewProps = {
  datasetId?: string | null;
  attributeKey?: string | null;
  tid?: number;
  dggsName?: string | null;
  layerStyle?: LayerStyle;
  mode: 'viewport' | 'operation';
  overrideCells?: CellRecord[];
  levelClamp?: LevelClamp;
  levelOverride?: number | null;
  relativeDepth?: number;
  useGlobe?: boolean;
  basemapStyle?: string;
  globeTexture?: string;
  onStats?: (stats: MapStats) => void;
  onCoordinatesChange?: (coords: { lat: number; lng: number } | null) => void;
  onZoomChange?: (zoom: number) => void;
};

const getInterpolator = (rampName?: string) => {
  switch (rampName) {
    case 'plasma': return interpolatePlasma;
    case 'magma': return interpolateMagma;
    case 'inferno': return interpolateInferno;
    case 'temperature': return interpolateRdBu; // Red-Blue divergence for temperature
    case 'elevation': return interpolateSpectral; // Spectral often used for topography
    case 'bathymetry': return interpolateBlues; // Blues for water depth
    case 'viridis':
    default:
      return interpolateViridis;
  }
};

const clampLat = (lat: number) => Math.max(-85, Math.min(85, lat));

const getGlobeVisibleBounds = (viewState: MapViewState): GeoExtent => {
  const { latitude = 0, longitude = 0, zoom = 1 } = viewState;
  const span = 360 / Math.pow(2, Math.max(0, zoom - 1.5));
  const halfSpan = span / 2;
  return {
    ll: { lat: Math.max(-85, latitude - halfSpan), lon: longitude - halfSpan },
    ur: { lat: Math.min(85, latitude + halfSpan), lon: longitude + halfSpan },
  };
};

const buildExtent = (viewState: MapViewState, width: number, height: number, useGlobe: boolean): GeoExtent => {
  // For globe view, use adaptive bounds if zoomed in
  if (useGlobe) {
    if ((viewState.zoom ?? 0) > 3) {
      return getGlobeVisibleBounds(viewState);
    }
    return {
      ll: { lat: -85, lon: -180 },
      ur: { lat: 85, lon: 180 },
    };
  }

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
  dggsName,
  layerStyle,
  mode,
  overrideCells = [],
  levelClamp,
  levelOverride,
  relativeDepth,
  useGlobe = false,
  basemapStyle,
  globeTexture,
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
  const lastLevel = useRef<number>(0);
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

  const [loadingNewLevel, setLoadingNewLevel] = useState(false);

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

    // Determine target level
    let targetLevel = levelOverride ?? 1;
    if (!levelOverride) {
      const zoomLevel = viewState.zoom ?? 0;
      targetLevel = Math.max(1, Math.floor(zoomLevel));
    }
    const effectiveMinLevel = useGlobe ? Math.max(levelClamp?.min ?? 0, 1) : levelClamp?.min;
    const effectiveMaxLevel = useGlobe ? Math.min(levelClamp?.max ?? 10, 10) : levelClamp?.max;
    if (effectiveMinLevel !== undefined) targetLevel = Math.max(effectiveMinLevel, targetLevel);
    if (effectiveMaxLevel !== undefined) targetLevel = Math.min(effectiveMaxLevel, targetLevel);

    const extent = buildExtent(viewState, size.width, size.height, useGlobe);
    const extentKey = [
      extent.ll.lat.toFixed(4),
      extent.ll.lon.toFixed(4),
      extent.ur.lat.toFixed(4),
      extent.ur.lon.toFixed(4),
      targetLevel, // Include targetLevel in key to detect level changes
      relativeDepth ?? 0,
      datasetId,
      attributeKey,
      tid,
    ].join('|');
    if (extentKey === lastViewportKey.current) {
      return;
    }
    lastViewportKey.current = extentKey;

    onStats?.({ zoneCount: 0, cellCount: 0, status: 'Resolving viewport...' });

    // Check for level change
    const levelChanged = targetLevel !== lastLevel.current;
    if (levelChanged) {
      console.log(`[MapView] Level change detected: ${lastLevel.current} -> ${targetLevel}. Clearing polygons.`);
      setLoadingNewLevel(true); // Flag to block rendering of old data
      setViewportCells([]);
      setPolygons([]);
      lastLevel.current = targetLevel;
    }

    console.log(`[MapView] Zoom: ${viewState.zoom?.toFixed(2)}, Level: ${targetLevel}, Limits: ${effectiveMinLevel}-${effectiveMaxLevel}`);

    // Use backend for zone enumeration to ensure consistency with stored data
    const bboxArr: [number, number, number, number] = [
      extent.ll.lat, extent.ll.lon, extent.ur.lat, extent.ur.lon
    ];

    let zoneIds: string[];
    let level: number;
    try {
      const result = await listZonesFromBackend(
        targetLevel,
        bboxArr,
        dggsName ?? undefined,
        useGlobe ? 1500 : 2600
      );
      zoneIds = result.zones;
      level = result.level;
      console.log(`[MapView] Backend returned ${zoneIds.length} zones at level ${level}`);
    } catch (err) {
      console.error('[MapView] Failed to list zones from backend:', err);
      if (levelChanged) setLoadingNewLevel(false); // Reset on error
      setViewportCells([]);
      onStats?.({ zoneCount: 0, cellCount: 0, status: 'Zone listing failed' });
      return;
    }

    if (!zoneIds.length) {
      if (levelChanged) setLoadingNewLevel(false);
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
      if (levelChanged) setLoadingNewLevel(false);
      throw err;
    }

    if (currentRequest !== requestId.current) {
      return;
    }

    const cells = result.cells ?? [];
    setViewportCells(cells);
    // Note: setLoadingNewLevel(false) happens when polygons are built in the other hook?
    // Actually, we should reset it here, but policies rely on `activeCells`.
    // The polygon build effect depends on `activeCells`.
    // If we set `activeCells` (viewportCells), that effect triggers.
    // If we set `loadingNewLevel(false)` here, the polygons might not be ready yet.
    // Ideally, we wait for polygons?
    // But `setPolygons` is async in effect.
    // Let's reset it here, assuming `setPolygons([])` earlier cleared the view.
    // The `isLoading` flag was mainly to FORCE distinct breakdown.
    setLoadingNewLevel(false);

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
    useGlobe,
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
        { concurrency: 16, signal: controller.signal, dggsName: dggsName ?? undefined }
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
        getZoneLevel(record.cell.dggid, dggsName ?? undefined),
        getNeighbors(record.cell.dggid, dggsName ?? undefined),
        getParent(record.cell.dggid, dggsName ?? undefined),
        getChildren(record.cell.dggid, dggsName ?? undefined),
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
      const selectionMap = await resolveZonePolygons(selectionIds, 3, { concurrency: 8, dggsName: dggsName ?? undefined });
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

  // Memoize the color scale to avoid recreating it for every cell
  const colorScale = useMemo(() => {
    const rampName = layerStyle?.colorRamp ?? 'viridis';
    const minVal = layerStyle?.minValue ?? -10;
    const maxVal = layerStyle?.maxValue ?? 10;
    const interpolator = getInterpolator(rampName);
    return scaleSequential(interpolator).domain([minVal, maxVal]);
  }, [layerStyle?.colorRamp, layerStyle?.minValue, layerStyle?.maxValue]);

  const layers = useMemo<Layer[]>(() => {
    const layerList: Layer[] = [];

    // Add earth background for globe view using BitmapLayer
    if (useGlobe) {
      layerList.push(
        new BitmapLayer({
          id: 'earth-texture',
          bounds: [-180, -90, 180, 90],
          image: globeTexture ?? EARTH_TEXTURE_URL,
        })
      );
    }

    // DGGS cells layer - coordinateSystem defaults to LNGLAT which works for globe
    const styleOpacity = layerStyle?.opacity ?? 1;
    // Don't render if visible is false OR if we are in the middle of a level loading transition
    const dataToRender = (layerStyle?.visible === false || loadingNewLevel) ? [] : polygons;
    layerList.push(
      new PolygonLayer<PolygonRecord>({
        id: `dggs-polygons-${lastLevel.current}`,
        data: dataToRender,
        opacity: styleOpacity,
        getPolygon: (d) => d.polygon,
        getFillColor: (d) => {
          if (layerStyle?.color) {
            return [...layerStyle.color, 255] as Color;
          }
          // Use value-based coloring with dataset min/max
          const val = d.cell.value_num;
          if (val === null || val === undefined || Number.isNaN(val)) {
            return [200, 200, 200, 100] as Color; // Grey for missing data
          }
          const colorStr = colorScale(val);
          const parsed = rgb(colorStr);
          return [parsed.r, parsed.g, parsed.b, 255] as Color;
        },
        getLineColor: [255, 255, 255, 80],
        lineWidthMinPixels: 1,
        pickable: true,
        autoHighlight: true,
        coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
      }),
    );

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
          coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
        })
      );
    }

    return layerList;
  }, [polygons, selectionPolygons, useGlobe, layerStyle]);

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
            mapStyle={basemapStyle ?? BASEMAP_STYLE}
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
