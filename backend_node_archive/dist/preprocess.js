import { parse } from 'csv-parse/sync';
import { minio } from './minio.js';
import { config } from './config.js';
import { query } from './db.js';
import { ingestRasterBuffer } from './gebco.js';
import { loadDggal } from './dggal.js';
const streamToBuffer = async (stream) => {
    const chunks = [];
    for await (const chunk of stream) {
        chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    return Buffer.concat(chunks);
};
const toCellRecord = (raw, fallbackAttrKey) => {
    const dggid = String(raw.dggid ?? raw.dggId ?? raw.zone ?? '').trim();
    if (!dggid) {
        return null;
    }
    const attrKey = String(raw.attr_key ?? raw.key ?? raw.attribute ?? raw.attr ?? fallbackAttrKey ?? '').trim();
    if (!attrKey) {
        return null;
    }
    const tid = Number(raw.tid ?? raw.time ?? 0);
    let valueText = null;
    let valueNum = null;
    let valueJson = null;
    const valueCandidate = raw.value ?? raw.value_text ?? raw.value_num ?? raw.value_json ?? null;
    if (typeof raw.value_num === 'number') {
        valueNum = raw.value_num;
    }
    else if (typeof valueCandidate === 'number') {
        valueNum = valueCandidate;
    }
    else if (valueCandidate !== null && valueCandidate !== undefined) {
        const asString = String(valueCandidate);
        const trimmed = asString.trim();
        if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
            try {
                valueJson = JSON.parse(trimmed);
            }
            catch {
                valueText = asString;
            }
        }
        else {
            const maybeNumber = Number(trimmed);
            if (!Number.isNaN(maybeNumber)) {
                valueNum = maybeNumber;
            }
            else {
                valueText = asString;
            }
        }
    }
    return {
        dggid,
        tid: Number.isFinite(tid) ? tid : 0,
        attr_key: attrKey,
        value_text: valueText,
        value_num: valueNum,
        value_json: valueJson,
    };
};
const insertCells = async (datasetId, cells) => {
    const chunkSize = 500;
    for (let i = 0; i < cells.length; i += chunkSize) {
        const chunk = cells.slice(i, i + chunkSize);
        const values = [];
        const rows = chunk
            .map((cell, index) => {
            const base = index * 7;
            values.push(datasetId, cell.dggid, cell.tid, cell.attr_key, cell.value_text, cell.value_num, cell.value_json ? JSON.stringify(cell.value_json) : null);
            return `($${base + 1}, $${base + 2}, $${base + 3}, $${base + 4}, $${base + 5}, $${base + 6}, $${base + 7})`;
        })
            .join(',');
        await query(`INSERT INTO cell_objects (dataset_id, dggid, tid, attr_key, value_text, value_num, value_json)
       VALUES ${rows}
       ON CONFLICT (dataset_id, dggid, tid, attr_key)
       DO UPDATE SET value_text = EXCLUDED.value_text, value_num = EXCLUDED.value_num, value_json = EXCLUDED.value_json`, values);
    }
};
const updateDatasetMetadata = async (datasetId, patch) => {
    const current = await query('SELECT metadata FROM datasets WHERE id = $1', [
        datasetId,
    ]);
    const metadata = current.rows[0]?.metadata ?? {};
    await query('UPDATE datasets SET metadata = $1 WHERE id = $2', [{ ...metadata, ...patch }, datasetId]);
};
const getDatasetContext = async (job) => {
    const result = await query('SELECT name, metadata FROM datasets WHERE id = $1', [job.datasetId]);
    const row = result.rows[0];
    const metadata = row?.metadata ?? {};
    const fallbackAttrKey = row?.name?.toLowerCase().includes('gebco') ? 'gebco_depth' : 'value';
    return {
        name: row?.name ?? 'Dataset',
        metadata,
        attrKey: job.attrKey ?? metadata.attr_key ?? fallbackAttrKey,
        minLevel: job.minLevel ?? metadata.min_level,
        maxLevel: job.maxLevel ?? metadata.max_level,
    };
};
const computeLevelRange = async (cells) => {
    if (!cells.length)
        return { minLevel: undefined, maxLevel: undefined };
    const dggal = await loadDggal();
    const dggrs = dggal.createDGGRS('IVEA3H');
    let minLevel = Number.POSITIVE_INFINITY;
    let maxLevel = Number.NEGATIVE_INFINITY;
    for (const cell of cells) {
        const zone = dggrs.getZoneFromTextID(cell.dggid);
        const level = dggrs.getZoneLevel(zone);
        if (Number.isFinite(level)) {
            minLevel = Math.min(minLevel, level);
            maxLevel = Math.max(maxLevel, level);
        }
    }
    dggal.terminate();
    if (!Number.isFinite(minLevel) || !Number.isFinite(maxLevel)) {
        return { minLevel: undefined, maxLevel: undefined };
    }
    return { minLevel, maxLevel };
};
const geometryCentroid = (geometry) => {
    if (!geometry)
        return null;
    if (geometry.type === 'Point' && Array.isArray(geometry.coordinates)) {
        const [lon, lat] = geometry.coordinates;
        return { lon, lat };
    }
    const coords = geometry.coordinates;
    if (!coords)
        return null;
    const flatten = (arr) => {
        if (typeof arr[0] === 'number')
            return [arr];
        return arr.flatMap((item) => flatten(item));
    };
    const points = flatten(coords).filter((point) => point.length >= 2);
    if (!points.length)
        return null;
    let minLon = points[0][0];
    let maxLon = points[0][0];
    let minLat = points[0][1];
    let maxLat = points[0][1];
    for (const point of points) {
        minLon = Math.min(minLon, point[0]);
        maxLon = Math.max(maxLon, point[0]);
        minLat = Math.min(minLat, point[1]);
        maxLat = Math.max(maxLat, point[1]);
    }
    return {
        lon: (minLon + maxLon) / 2,
        lat: (minLat + maxLat) / 2,
    };
};
const ingestVectorGeoJSON = async (datasetId, parsed, attrKey, level) => {
    const features = Array.isArray(parsed?.features) ? parsed.features : Array.isArray(parsed) ? parsed : [];
    if (!features.length) {
        throw new Error('GeoJSON has no features to ingest.');
    }
    const dggal = await loadDggal();
    const dggrs = dggal.createDGGRS('IVEA3H');
    const cells = [];
    for (const feature of features) {
        const props = feature?.properties ?? {};
        let dggid = props.dggid || props.DGGID || props.zone;
        if (!dggid) {
            const centroid = geometryCentroid(feature.geometry);
            if (!centroid)
                continue;
            const zone = dggrs.getZoneFromWGS84Centroid(level, centroid);
            dggid = dggrs.getZoneTextID(zone);
        }
        const rawValue = props[attrKey] ?? props.value ?? 1;
        const valueNum = typeof rawValue === 'number' ? rawValue : Number(rawValue);
        const valueText = Number.isNaN(valueNum) ? String(rawValue) : null;
        cells.push({
            dggid: String(dggid),
            tid: Number(props.tid ?? 0),
            attr_key: attrKey,
            value_text: valueText,
            value_num: Number.isNaN(valueNum) ? null : valueNum,
            value_json: null,
        });
    }
    dggal.terminate();
    await insertCells(datasetId, cells);
    return cells;
};
export const preprocessUpload = async (job) => {
    await query('UPDATE uploads SET status = $1, updated_at = now() WHERE id = $2', ['processing', job.uploadId]);
    try {
        const datasetContext = await getDatasetContext(job);
        const stream = await minio.getObject(config.minio.bucket, job.storageKey);
        const buffer = await streamToBuffer(stream);
        const extension = job.filename.split('.').pop()?.toLowerCase();
        if (extension === 'tif' || extension === 'tiff' || job.mimeType.includes('tiff')) {
            await ingestRasterBuffer({
                datasetId: job.datasetId,
                buffer,
                attrKey: datasetContext.attrKey,
                minLevel: datasetContext.minLevel,
                maxLevel: datasetContext.maxLevel,
                source: job.storageKey,
            });
            await updateDatasetMetadata(job.datasetId, {
                source_type: 'raster',
                attr_key: datasetContext.attrKey,
            });
            await query('UPDATE datasets SET status = $1 WHERE id = $2', ['active', job.datasetId]);
            await query('UPDATE uploads SET status = $1, updated_at = now() WHERE id = $2', ['processed', job.uploadId]);
            return;
        }
        let records = [];
        if (extension === 'csv') {
            records = parse(buffer, {
                columns: true,
                skip_empty_lines: true,
                trim: true,
            });
        }
        else if (extension === 'geojson' || extension === 'json' || job.mimeType.includes('json')) {
            const parsed = JSON.parse(buffer.toString('utf-8'));
            if (parsed?.type === 'FeatureCollection' || Array.isArray(parsed?.features)) {
                const level = datasetContext.minLevel ?? datasetContext.maxLevel ?? 4;
                const cells = await ingestVectorGeoJSON(job.datasetId, parsed, datasetContext.attrKey, level);
                await updateDatasetMetadata(job.datasetId, {
                    min_level: level,
                    max_level: level,
                    source_type: 'vector',
                    attr_key: datasetContext.attrKey,
                });
                await query('UPDATE datasets SET status = $1 WHERE id = $2', ['active', job.datasetId]);
                await query('UPDATE uploads SET status = $1, updated_at = now() WHERE id = $2', ['processed', job.uploadId]);
                return;
            }
            if (Array.isArray(parsed)) {
                records = parsed;
            }
            else if (Array.isArray(parsed?.cells)) {
                records = parsed.cells;
            }
            else {
                throw new Error('JSON format not recognized. Expected array, FeatureCollection, or {"cells": [...] }');
            }
        }
        else {
            throw new Error('Unsupported file format. Use CSV, GeoJSON, or TIFF/COG.');
        }
        const cells = records
            .map((record) => toCellRecord(record, datasetContext.attrKey))
            .filter((cell) => cell !== null);
        if (!cells.length) {
            throw new Error('No valid cell records found in file.');
        }
        await insertCells(job.datasetId, cells);
        const levelRange = await computeLevelRange(cells);
        await updateDatasetMetadata(job.datasetId, {
            min_level: levelRange.minLevel ?? datasetContext.minLevel,
            max_level: levelRange.maxLevel ?? datasetContext.maxLevel,
            source_type: job.sourceType ?? 'table',
            attr_key: datasetContext.attrKey,
        });
        await query('UPDATE datasets SET status = $1 WHERE id = $2', ['active', job.datasetId]);
        await query('UPDATE uploads SET status = $1, updated_at = now() WHERE id = $2', ['processed', job.uploadId]);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown preprocessing error';
        await query('UPDATE uploads SET status = $1, error = $2, updated_at = now() WHERE id = $3', [
            'failed',
            message,
            job.uploadId,
        ]);
    }
};
