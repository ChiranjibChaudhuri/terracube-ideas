export type DggalModule = {
  DGGAL: {
    init: () => Promise<DggalInstance>;
    nullZone: bigint;
  };
};

type DggalInstance = {
  createDGGRS: (name: string) => DggrsInstance;
};

type DggrsInstance = {
  getZoneFromTextID: (zoneId: string) => bigint;
  getZoneRefinedWGS84Vertices: (zone: bigint, edgeRefinement: number) => { lat: number; lon: number }[];
  getZoneTextID: (zone: bigint) => string;
  getZoneLevel: (zone: bigint) => number;
  listZones: (level: number, bbox: GeoExtent) => bigint[];
  getLevelFromPixelsAndExtent: (extent: GeoExtent, width: number, height: number, relativeDepth: number) => number;
};

export type GeoExtent = {
  ll: { lat: number; lon: number };
  ur: { lat: number; lon: number };
};

let dggalPromise: Promise<DggalInstance> | null = null;
const dggrsPromises = new Map<string, Promise<DggrsInstance>>();
let nullZoneValue: bigint | null = null;
const polygonCache = new Map<string, number[][]>();
const polygonInflight = new Map<string, Promise<number[][] | null>>();
const POLYGON_CACHE_MAX_SIZE = 10000; // LRU-style limit to prevent memory leaks

const evictOldCacheEntries = () => {
  if (polygonCache.size > POLYGON_CACHE_MAX_SIZE) {
    // Evict oldest 25% of entries
    const keysToDelete = Array.from(polygonCache.keys()).slice(0, Math.floor(POLYGON_CACHE_MAX_SIZE * 0.25));
    keysToDelete.forEach(key => polygonCache.delete(key));
  }
};

export const loadDggal = async () => {
  if (!dggalPromise) {
    const url = '/dggal/dggal.js';
    dggalPromise = import(/* @vite-ignore */ url).then(async (mod: DggalModule) => {
      const dggal = await mod.DGGAL.init();
      nullZoneValue = mod.DGGAL.nullZone;
      return dggal;
    });
  }
  return dggalPromise;
};

export const loadDggrs = async (systemName: string) => {
  const key = systemName.toUpperCase();
  if (!dggrsPromises.has(key)) {
    dggrsPromises.set(key, loadDggal().then((dggal) => dggal.createDGGRS(key)));
  }
  return dggrsPromises.get(key)!;
};

export const loadIvea3h = async () => loadDggrs('IVEA3H');

export const zoneToPolygon = async (zoneId: string, refinement = 3, dggsName = 'IVEA3H') => {
  const cacheKey = `${dggsName}:${zoneId}:${refinement}`;
  const cached = polygonCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const inflight = polygonInflight.get(cacheKey);
  if (inflight) {
    return inflight;
  }
  const task = (async () => {
    try {
      const dggrs = await loadDggrs(dggsName);
      const zone = dggrs.getZoneFromTextID(zoneId);
      if (nullZoneValue !== null && zone === nullZoneValue) {
        console.warn(`[DGGAL] Invalid zone ID: ${zoneId}`);
        return null;
      }
      const vertices = dggrs.getZoneRefinedWGS84Vertices(zone, refinement);
      if (!vertices.length) {
        console.warn(`[DGGAL] No vertices for zone: ${zoneId}`);
        return null;
      }

      // Validate vertices - filter out any (0,0) points which indicate WASM read errors
      const validVertices = vertices.filter((v) => {
        // Check for invalid coordinates (exactly 0,0 or NaN)
        if (Number.isNaN(v.lat) || Number.isNaN(v.lon)) {
          console.warn(`[DGGAL] NaN coordinates for zone ${zoneId}`);
          return false;
        }
        // A single point at exactly 0,0 is suspicious - but allow if other points are valid
        return true;
      });

      if (validVertices.length < 3) {
        console.warn(`[DGGAL] Insufficient valid vertices (${validVertices.length}) for zone: ${zoneId}`);
        return null;
      }

      // Check if all vertices are at 0,0 (indicates WASM initialization issue)
      const allZero = validVertices.every((v) => v.lat === 0 && v.lon === 0);
      if (allZero) {
        console.warn(`[DGGAL] All vertices at (0,0) for zone ${zoneId} - WASM may not be initialized properly`);
        return null;
      }

      // DGGAL returns coordinates in radians - convert to degrees for GeoJSON/Deck.gl
      const RAD_TO_DEG = 180 / Math.PI;
      const ring = validVertices.map((v) => [v.lon * RAD_TO_DEG, v.lat * RAD_TO_DEG]);
      const first = ring[0];
      const last = ring[ring.length - 1];
      if (first[0] !== last[0] || first[1] !== last[1]) {
        ring.push(first);
      }
      polygonCache.set(cacheKey, ring);
      evictOldCacheEntries(); // Maintain cache size limit
      return ring;
    } catch (err) {
      console.error(`[DGGAL] Error resolving polygon for zone ${zoneId}:`, err);
      return null;
    } finally {
      polygonInflight.delete(cacheKey);
    }
  })();
  polygonInflight.set(cacheKey, task);
  return task;
};

export const getZoneLevel = async (zoneId: string, dggsName = 'IVEA3H') => {
  const dggrs = await loadDggrs(dggsName);
  const zone = dggrs.getZoneFromTextID(zoneId);
  if (nullZoneValue !== null && zone === nullZoneValue) {
    return null;
  }
  return dggrs.getZoneLevel(zone);
};

export const resolveZonePolygons = async (
  zoneIds: string[],
  refinement = 3,
  options: {
    concurrency?: number;
    signal?: AbortSignal;
    useSpatialDb?: boolean;
    dggsName?: string;
  } = {}
) => {
  const uniqueZones = Array.from(new Set(zoneIds));
  const results = new Map<string, number[][]>();
  const concurrency = Math.max(1, options.concurrency ?? 12);
  const useSpatialDb = options.useSpatialDb ?? true;
  const dggsName = options.dggsName ?? 'IVEA3H';

  // Try to load from spatial database first (if enabled)
  let zonesToResolve = uniqueZones;
  if (useSpatialDb) {
    try {
      const { getPolygons, storePolygons } = await import('./spatialDb');
      const cached = await getPolygons(uniqueZones);

      // Add cached polygons to results
      for (const [zoneId, polygon] of cached) {
        results.set(zoneId, polygon);
      }

      // Filter out already cached zones
      zonesToResolve = uniqueZones.filter(id => !cached.has(id));

      if (cached.size > 0) {
        console.log(`[DGGAL] Loaded ${cached.size} polygons from spatial DB, ${zonesToResolve.length} to resolve`);
      }
    } catch (err) {
      console.warn('[DGGAL] Spatial DB not available, using in-memory cache:', err);
    }
  }

  // Resolve remaining zones via WASM
  let index = 0;
  const newPolygons = new Map<string, number[][]>();

  const worker = async () => {
    while (index < zonesToResolve.length) {
      if (options.signal?.aborted) {
        return;
      }
      const zoneId = zonesToResolve[index];
      index += 1;
      const polygon = await zoneToPolygon(zoneId, refinement, dggsName);
      if (options.signal?.aborted) {
        return;
      }
      if (polygon) {
        results.set(zoneId, polygon);
        newPolygons.set(zoneId, polygon);
      }
    }
  };

  const workerCount = Math.min(concurrency, zonesToResolve.length);
  if (workerCount > 0) {
    await Promise.all(Array.from({ length: workerCount }, worker));
  }

  // Store newly resolved polygons in spatial DB for future use
  if (useSpatialDb && newPolygons.size > 0) {
    try {
      const { storePolygons } = await import('./spatialDb');
      await storePolygons(newPolygons, refinement);
      console.log(`[DGGAL] Stored ${newPolygons.size} polygons in spatial DB`);
    } catch (err) {
      console.warn('[DGGAL] Failed to store polygons in spatial DB:', err);
    }
  }

  return results;
};

export const listZoneIdsForExtent = async (
  extent: GeoExtent,
  width: number,
  height: number,
  options: {
    relativeDepth?: number;
    maxZones?: number;
    minLevel?: number;
    maxLevel?: number;
    levelOverride?: number;
    dggsName?: string;
  } = {}
) => {
  const dggrs = await loadDggrs(options.dggsName ?? 'IVEA3H');
  const relativeDepth = options.relativeDepth ?? 0;
  const maxZones = options.maxZones ?? 2400;

  let level = options.levelOverride ?? dggrs.getLevelFromPixelsAndExtent(extent, width, height, relativeDepth);
  level = Math.max(0, level);
  if (options.maxLevel !== undefined) {
    level = Math.min(level, options.maxLevel);
  }
  if (options.minLevel !== undefined) {
    level = Math.max(level, options.minLevel);
  }

  let zones = dggrs.listZones(level, extent);
  const minLevel = options.minLevel ?? 0;
  while (zones.length > maxZones && level > minLevel) {
    level -= 1;
    zones = dggrs.listZones(level, extent);
  }

  const zoneIds = zones.map((zone) => dggrs.getZoneTextID(zone));
  return { level, zones, zoneIds };
};
