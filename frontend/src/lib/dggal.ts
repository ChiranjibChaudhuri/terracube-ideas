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
let dggrsPromise: Promise<DggrsInstance> | null = null;
let nullZoneValue: bigint | null = null;
const polygonCache = new Map<string, number[][]>();
const polygonInflight = new Map<string, Promise<number[][] | null>>();

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

export const loadIvea3h = async () => {
  if (!dggrsPromise) {
    dggrsPromise = loadDggal().then((dggal) => dggal.createDGGRS('IVEA3H'));
  }
  return dggrsPromise;
};

export const zoneToPolygon = async (zoneId: string, refinement = 3) => {
  const cacheKey = `${zoneId}:${refinement}`;
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
      const dggrs = await loadIvea3h();
      const zone = dggrs.getZoneFromTextID(zoneId);
      if (nullZoneValue !== null && zone === nullZoneValue) {
        return null;
      }
      const vertices = dggrs.getZoneRefinedWGS84Vertices(zone, refinement);
      if (!vertices.length) {
        return null;
      }
      const ring = vertices.map((v) => [v.lon, v.lat]);
      const first = ring[0];
      const last = ring[ring.length - 1];
      if (first[0] !== last[0] || first[1] !== last[1]) {
        ring.push(first);
      }
      polygonCache.set(cacheKey, ring);
      return ring;
    } finally {
      polygonInflight.delete(cacheKey);
    }
  })();
  polygonInflight.set(cacheKey, task);
  return task;
};

export const getZoneLevel = async (zoneId: string) => {
  const dggrs = await loadIvea3h();
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
  } = {}
) => {
  const uniqueZones = Array.from(new Set(zoneIds));
  const results = new Map<string, number[][]>();
  const concurrency = Math.max(1, options.concurrency ?? 12);
  let index = 0;

  const worker = async () => {
    while (index < uniqueZones.length) {
      if (options.signal?.aborted) {
        return;
      }
      const zoneId = uniqueZones[index];
      index += 1;
      const polygon = await zoneToPolygon(zoneId, refinement);
      if (options.signal?.aborted) {
        return;
      }
      if (polygon) {
        results.set(zoneId, polygon);
      }
    }
  };

  const workerCount = Math.min(concurrency, uniqueZones.length);
  await Promise.all(Array.from({ length: workerCount }, worker));
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
  } = {}
) => {
  const dggrs = await loadIvea3h();
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
