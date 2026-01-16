import { fromArrayBuffer, type GeoTIFFImage } from 'geotiff';
import fs from 'node:fs/promises';
import { query } from './db.js';
import { config } from './config.js';
import { loadDggal, type GeoExtent, type GeoPoint } from './dggal.js';

type RasterCatalogEntry = {
  id: number;
  image: GeoTIFFImage;
  width: number;
  height: number;
  bbox: GeoExtent;
  levelHint: number;
};

type RasterData = {
  width: number;
  height: number;
  bbox: GeoExtent;
  data: Float32Array | number[];
  noData: number | null;
};

type RasterIngestOptions = {
  datasetId: string;
  buffer?: Buffer;
  source?: string;
  attrKey: string;
  minLevel?: number;
  maxLevel?: number;
  maxZonesPerLevel?: number;
  maxImagePixels?: number;
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const buildExtent = (bbox: number[]): GeoExtent => {
  const [minX, minY, maxX, maxY] = bbox;
  return {
    ll: { lon: minX, lat: minY },
    ur: { lon: maxX, lat: maxY },
  };
};

const loadRasterCatalog = async (image: GeoTIFFImage, dggrs: any) => {
  const baseBbox = image.getBoundingBox();
  const extent = buildExtent(baseBbox);
  const images: GeoTIFFImage[] = [image, ...(image as any).getOverviews()];

  return images.map((img, index) => {
    const width = img.getWidth();
    const height = img.getHeight();
    const levelHint = dggrs.getLevelFromPixelsAndExtent(extent, width, height, 0);
    return {
      id: index,
      image: img,
      width,
      height,
      bbox: extent,
      levelHint,
    };
  });
};

const selectCatalogEntry = (catalog: RasterCatalogEntry[], level: number) => {
  return catalog.reduce((best, entry) => {
    if (!best) return entry;
    const currentDelta = Math.abs(entry.levelHint - level);
    const bestDelta = Math.abs(best.levelHint - level);
    return currentDelta < bestDelta ? entry : best;
  }, null as RasterCatalogEntry | null);
};

const loadRasterData = async (
  entry: RasterCatalogEntry,
  maxPixels: number,
  cache: Map<number, RasterData>
) => {
  if (cache.has(entry.id)) {
    return cache.get(entry.id) as RasterData;
  }

  let width = entry.width;
  let height = entry.height;
  const totalPixels = width * height;
  if (totalPixels > maxPixels) {
    const scale = Math.sqrt(maxPixels / totalPixels);
    width = Math.max(1, Math.floor(width * scale));
    height = Math.max(1, Math.floor(height * scale));
  }

  const rasters = (await entry.image.readRasters({
    width,
    height,
    interleave: true,
    resampleMethod: 'bilinear',
  })) as Float32Array | number[];

  const data: RasterData = {
    width,
    height,
    bbox: entry.bbox,
    data: rasters,
    noData: entry.image.getGDALNoData() ?? null,
  };
  cache.set(entry.id, data);
  return data;
};

const sampleRaster = (raster: RasterData, point: GeoPoint) => {
  const { ll, ur } = raster.bbox;
  if (point.lon < ll.lon || point.lon > ur.lon || point.lat < ll.lat || point.lat > ur.lat) {
    return null;
  }

  const xRatio = (point.lon - ll.lon) / (ur.lon - ll.lon);
  const yRatio = (ur.lat - point.lat) / (ur.lat - ll.lat);
  const x = clamp(Math.floor(xRatio * (raster.width - 1)), 0, raster.width - 1);
  const y = clamp(Math.floor(yRatio * (raster.height - 1)), 0, raster.height - 1);

  const index = y * raster.width + x;
  const value = raster.data[index];
  if (value === undefined || Number.isNaN(value)) {
    return null;
  }
  if (raster.noData !== null && value === raster.noData) {
    return null;
  }
  return Number(value);
};

const insertCells = async (datasetId: string, attrKey: string, cells: Array<{ dggid: string; value: number }>) => {
  const chunkSize = 1000;
  for (let i = 0; i < cells.length; i += chunkSize) {
    const chunk = cells.slice(i, i + chunkSize);
    const values: unknown[] = [];
    const rows = chunk
      .map((cell, index) => {
        const base = index * 7;
        values.push(datasetId, cell.dggid, 0, attrKey, null, cell.value, null);
        return `($${base + 1}, $${base + 2}, $${base + 3}, $${base + 4}, $${base + 5}, $${base + 6}, $${base + 7})`;
      })
      .join(',');

    await query(
      `INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_text, value_num, value_json)
       VALUES ${rows}
       ON CONFLICT (dataset_id, dggid, tid, attr_key)
       DO UPDATE SET value_num = EXCLUDED.value_num`,
      values
    );
  }
};

const updateDatasetMetadata = async (datasetId: string, patch: Record<string, unknown>) => {
  const current = await query<{ metadata: Record<string, unknown> }>('SELECT metadata FROM datasets WHERE id = $1', [
    datasetId,
  ]);
  const metadata = current.rows[0]?.metadata ?? {};
  await query('UPDATE datasets SET metadata = $1 WHERE id = $2', [{ ...metadata, ...patch }, datasetId]);
};

export const ingestRasterBuffer = async (options: RasterIngestOptions) => {
  const maxZonesPerLevel = options.maxZonesPerLevel ?? config.gebco.maxZonesPerLevel;
  const maxImagePixels = options.maxImagePixels ?? config.gebco.maxImagePixels;

  if (!options.buffer) {
    throw new Error('Raster ingest requires a buffer.');
  }

  const arrayBuffer = options.buffer.buffer.slice(
    options.buffer.byteOffset,
    options.buffer.byteOffset + options.buffer.byteLength
  );

  const dggal = await loadDggal();
  const dggrs = dggal.createDGGRS('IVEA3H');

  const tiff = await fromArrayBuffer(arrayBuffer as ArrayBuffer);
  const image = await tiff.getImage();
  const extent = buildExtent(image.getBoundingBox());

  const catalog = await loadRasterCatalog(image, dggrs);
  const cache = new Map<number, RasterData>();

  const maxLevelAuto = dggrs.getLevelFromPixelsAndExtent(extent, image.getWidth(), image.getHeight(), 0);
  const minLevel = options.minLevel ?? Math.max(1, maxLevelAuto - 4);
  const maxLevel = options.maxLevel ?? maxLevelAuto;

  for (let level = minLevel; level <= maxLevel; level += 1) {
    const entry = selectCatalogEntry(catalog, level);
    if (!entry) {
      continue;
    }

    const zones = dggrs.listZones(level, extent);
    if (zones.length > maxZonesPerLevel) {
      continue;
    }

    const raster = await loadRasterData(entry, maxImagePixels, cache);
    const batch: Array<{ dggid: string; value: number }> = [];

    for (const zone of zones) {
      const centroid = dggrs.getZoneWGS84Centroid(zone);
      const value = sampleRaster(raster, centroid);
      if (value === null) continue;
      batch.push({ dggid: dggrs.getZoneTextID(zone), value });
      if (batch.length >= 1000) {
        await insertCells(options.datasetId, options.attrKey, batch.splice(0, batch.length));
      }
    }

    if (batch.length) {
      await insertCells(options.datasetId, options.attrKey, batch.splice(0, batch.length));
    }
  }

  await updateDatasetMetadata(options.datasetId, {
    min_level: minLevel,
    max_level: maxLevel,
    source: options.source ?? 'minio',
    source_type: 'raster',
    attr_key: options.attrKey,
  });

  dggal.terminate();
  return { minLevel, maxLevel };
};

export const bootstrapGebco = async () => {
  const pathOrUrl = config.gebco.path || config.gebco.url;
  if (!pathOrUrl) {
    console.warn('GEBCO data init skipped: no GEBCO_PATH or GEBCO_URL configured.');
    return;
  }

  const existing = await query<{ id: string; metadata: any }>('SELECT id, metadata FROM datasets WHERE name = $1', [
    'GEBCO Bathymetry',
  ]);

  let datasetId = existing.rows[0]?.id;
  const metadata = existing.rows[0]?.metadata ?? {};
  if (metadata.gebco_loaded) {
    console.log('GEBCO dataset already loaded; skipping ingestion.');
    return;
  }

  if (!datasetId) {
    const created = await query<{ id: string }>(
      'INSERT INTO datasets (name, description, dggs_name, status, metadata) VALUES ($1, $2, $3, $4, $5) RETURNING id',
      [
        'GEBCO Bathymetry',
        'GEBCO global bathymetry grid sampled into IVEA3H DGGS cells.',
        'IVEA3H',
        'loading',
        { source: pathOrUrl },
      ]
    );
    datasetId = created.rows[0].id;
  } else {
    await query('UPDATE datasets SET status = $1 WHERE id = $2', ['loading', datasetId]);
  }

  await query(
    'INSERT INTO attributes (key, description, unit, data_type) VALUES ($1, $2, $3, $4) ON CONFLICT (key) DO NOTHING',
    ['gebco_depth', 'GEBCO bathymetry depth', 'meters', 'number']
  );

  let buffer: Buffer;
  if (config.gebco.path) {
    buffer = await fs.readFile(config.gebco.path);
  } else {
    const response = await fetch(config.gebco.url);
    if (!response.ok) {
      throw new Error(`Failed to download GEBCO COG: ${response.status}`);
    }
    buffer = Buffer.from(await response.arrayBuffer());
  }

  await ingestRasterBuffer({
    datasetId,
    buffer,
    attrKey: 'gebco_depth',
    minLevel: config.gebco.minLevel,
    maxLevel: config.gebco.maxLevel,
    source: pathOrUrl,
  });

  await updateDatasetMetadata(datasetId, {
    ...metadata,
    gebco_loaded: true,
  });

  await query('UPDATE datasets SET status = $1 WHERE id = $2', ['active', datasetId]);
  console.log('GEBCO ingestion complete.');
};
