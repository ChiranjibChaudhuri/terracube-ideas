import fs from 'node:fs/promises';
import { ensureBucket, minio } from '../src/minio.js';
import { preprocessQueue } from '../src/queue.js';
import { config } from '../src/config.js';
import { query } from '../src/db.js';

const getEnv = (key: string, fallback?: string) => process.env[key] ?? fallback;

const run = async () => {
  const sourcePath = getEnv('GEBCO_PATH');
  const sourceUrl = getEnv('GEBCO_URL');
  const datasetName = getEnv('DATA_INIT_NAME', 'GEBCO Bathymetry');
  const attrKey = getEnv('DATA_INIT_ATTR_KEY', 'gebco_depth');
  const minLevel = getEnv('GEBCO_MIN_LEVEL');
  const maxLevel = getEnv('GEBCO_MAX_LEVEL');

  if (!sourcePath && !sourceUrl) {
    console.error('Data init requires GEBCO_PATH or GEBCO_URL.');
    process.exitCode = 1;
    return;
  }

  await ensureBucket();

  const filename = sourcePath ? path.basename(sourcePath) : 'gebco_cog.tif';
  const storageKey = `data-init/${Date.now()}-${filename}`;

  if (sourcePath) {
    await minio.fPutObject(config.minio.bucket, storageKey, sourcePath, {
      'Content-Type': 'image/tiff',
    });
  } else if (sourceUrl) {
    const response = await fetch(sourceUrl);
    if (!response.ok) {
      throw new Error(`Failed to download ${sourceUrl}: ${response.status}`);
    }
    const buffer = Buffer.from(await response.arrayBuffer());
    await minio.putObject(config.minio.bucket, storageKey, buffer, buffer.length, {
      'Content-Type': 'image/tiff',
    });
  }

  const datasetResult = await query<{ id: string; metadata: Record<string, unknown> }>(
    'SELECT id, metadata FROM datasets WHERE name = $1',
    [datasetName]
  );

  let datasetId = datasetResult.rows[0]?.id;
  if (!datasetId) {
    const created = await query<{ id: string }>(
      'INSERT INTO datasets (name, description, dggs_name, status, metadata) VALUES ($1, $2, $3, $4, $5) RETURNING id',
      [
        datasetName,
        'DGGS-ingested raster dataset staged from MinIO.',
        'IVEA3H',
        'staged',
        {
          attr_key: attrKey,
          min_level: minLevel ? Number(minLevel) : undefined,
          max_level: maxLevel ? Number(maxLevel) : undefined,
          source_type: 'raster',
          source: sourcePath ?? sourceUrl,
        },
      ]
    );
    datasetId = created.rows[0].id;
  } else {
    const metadata = datasetResult.rows[0]?.metadata ?? {};
    await query('UPDATE datasets SET metadata = $1, status = $2 WHERE id = $3', [
      {
        ...metadata,
        attr_key: metadata.attr_key ?? attrKey,
        min_level: metadata.min_level ?? (minLevel ? Number(minLevel) : undefined),
        max_level: metadata.max_level ?? (maxLevel ? Number(maxLevel) : undefined),
        source_type: metadata.source_type ?? 'raster',
        source: metadata.source ?? sourcePath ?? sourceUrl,
      },
      'staged',
      datasetId,
    ]);
  }

  const uploadResult = await query<{ id: string }>(
    'INSERT INTO uploads (dataset_id, filename, mime_type, size_bytes, storage_key, status) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id',
    [datasetId, filename, 'image/tiff', null, storageKey, 'staged']
  );

  const uploadId = uploadResult.rows[0].id;

  await preprocessQueue.add('preprocess', {
    uploadId,
    datasetId,
    storageKey,
    filename,
    mimeType: 'image/tiff',
    attrKey,
    minLevel: minLevel ? Number(minLevel) : undefined,
    maxLevel: maxLevel ? Number(maxLevel) : undefined,
    sourceType: 'raster',
  });

  console.log(`Queued data init for ${datasetName} (upload ${uploadId}).`);
};

run().catch((error) => {
  console.error('Data init failed:', error);
  process.exitCode = 1;
});
