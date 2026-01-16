import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export type GeoPoint = { lat: number; lon: number };

export type GeoExtent = {
  ll: { lat: number; lon: number };
  ur: { lat: number; lon: number };
};

export type Dggrs = {
  listZones: (level: number, bbox: GeoExtent) => bigint[];
  getZoneTextID: (zone: bigint) => string;
  getZoneWGS84Centroid: (zone: bigint) => GeoPoint;
  getZoneFromWGS84Centroid: (level: number, point: GeoPoint) => bigint;
  getZoneFromTextID: (zoneId: string) => bigint;
  getZoneLevel: (zone: bigint) => number;
  getLevelFromPixelsAndExtent: (extent: GeoExtent, width: number, height: number, relativeDepth: number) => number;
  getZoneNeighbors: (zone: bigint) => Array<{ zone: bigint; type: number }>;
  getZoneParents: (zone: bigint) => bigint[];
  getZoneChildren: (zone: bigint) => bigint[];
  getZoneWGS84Vertices: (zone: bigint) => Array<{ lat: number; lon: number }>;
};

export type Dggal = {
  createDGGRS: (name: string) => Dggrs;
  terminate: () => void;
};

const fileDir = path.dirname(fileURLToPath(import.meta.url));
const dggalModulePath = path.resolve(fileDir, '../lib/dggal/dggal.js');

export const loadDggal = async (): Promise<Dggal> => {
  const mod = await import(pathToFileURL(dggalModulePath).href);
  const DGGALClass = mod.DGGAL ?? mod.default;
  return DGGALClass.init();
};
