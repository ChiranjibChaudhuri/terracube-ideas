/**
 * Browser Spatial Database using DuckDB-WASM
 * 
 * Provides PostGIS-like capabilities in the browser:
 * - Spatial geometry storage with WGS84 CRS
 * - Polygon caching for DGGS zones
 * - Spatial queries (intersects, contains, etc.)
 * - PROJ coordinate transformations
 */

import * as duckdb from '@duckdb/duckdb-wasm';

// Use stable version with proper CORS handling
const DUCKDB_BUNDLES: duckdb.DuckDBBundles = {
    mvp: {
        mainModule: 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/dist/duckdb-mvp.wasm',
        mainWorker: 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/dist/duckdb-browser-mvp.worker.js',
    },
    eh: {
        mainModule: 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/dist/duckdb-eh.wasm',
        mainWorker: 'https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/dist/duckdb-browser-eh.worker.js',
    },
};

type DuckDBConnection = duckdb.AsyncDuckDBConnection;
type DuckDBInstance = duckdb.AsyncDuckDB;

let dbInstance: DuckDBInstance | null = null;
let dbConnection: DuckDBConnection | null = null;
let spatialLoaded = false;
let initPromise: Promise<DuckDBConnection> | null = null;

const sanitizeSqlLiteral = (value: string) => value.replace(/'/g, "''");

/**
 * Create a same-origin worker from a CDN script URL using blob URL
 */
async function createBlobWorker(workerUrl: string): Promise<Worker> {
    const response = await fetch(workerUrl);
    if (!response.ok) {
        throw new Error(`Failed to fetch worker: ${response.statusText}`);
    }
    const workerScript = await response.text();
    const blob = new Blob([workerScript], { type: 'application/javascript' });
    const blobUrl = URL.createObjectURL(blob);
    return new Worker(blobUrl, { type: 'classic' });
}

/**
 * Initialize DuckDB-WASM with spatial extension
 */
export async function initSpatialDb(): Promise<DuckDBConnection> {
    if (initPromise) {
        return initPromise;
    }

    initPromise = (async () => {
        if (dbConnection) {
            return dbConnection;
        }

        console.log('[SpatialDB] Initializing DuckDB-WASM...');

        // Select best bundle for this browser
        const bundle = await duckdb.selectBundle(DUCKDB_BUNDLES);

        // Create worker using blob URL to avoid CORS issues
        const worker = await createBlobWorker(bundle.mainWorker!);
        const logger = new duckdb.ConsoleLogger();

        // Instantiate DuckDB
        dbInstance = new duckdb.AsyncDuckDB(logger, worker);
        await dbInstance.instantiate(bundle.mainModule);

        // Open database (in-memory)
        await dbInstance.open({ path: ':memory:' });

        // Create connection
        dbConnection = await dbInstance.connect();

        // Load spatial extension
        try {
            await dbConnection.query(`INSTALL spatial; LOAD spatial;`);
            spatialLoaded = true;
            console.log('[SpatialDB] Spatial extension loaded');
        } catch (err) {
            console.warn('[SpatialDB] Spatial extension not available, using basic mode:', err);
            spatialLoaded = false;
        }

        // Create polygon cache table
        await dbConnection.query(`
      CREATE TABLE IF NOT EXISTS dggs_polygons (
        zone_id VARCHAR PRIMARY KEY,
        refinement INTEGER,
        polygon_wkt TEXT,
        polygon_json TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp
      )
    `);

        console.log('[SpatialDB] Initialized successfully');
        return dbConnection;
    })();

    return initPromise;
}

/**
 * Store a DGGS polygon in the spatial database
 */
export async function storePolygon(
    zoneId: string,
    polygon: number[][],
    refinement: number = 3
): Promise<void> {
    const conn = await initSpatialDb();

    // Convert polygon to WKT format
    const coordinates = polygon.map(p => `${p[0]} ${p[1]}`).join(', ');
    const wkt = `POLYGON((${coordinates}))`;

    // Store as JSON for easy retrieval
    const json = JSON.stringify(polygon);

    await conn.query(`
    INSERT INTO dggs_polygons (zone_id, refinement, polygon_wkt, polygon_json)
    VALUES ('${sanitizeSqlLiteral(zoneId)}', ${refinement}, '${sanitizeSqlLiteral(wkt)}', '${sanitizeSqlLiteral(json)}')
    ON CONFLICT (zone_id) DO UPDATE SET
      refinement = EXCLUDED.refinement,
      polygon_wkt = EXCLUDED.polygon_wkt,
      polygon_json = EXCLUDED.polygon_json
  `);
}

/**
 * Retrieve a DGGS polygon from the spatial database
 */
export async function getPolygon(zoneId: string): Promise<number[][] | null> {
    const conn = await initSpatialDb();

    const result = await conn.query(`
    SELECT polygon_json FROM dggs_polygons WHERE zone_id = '${sanitizeSqlLiteral(zoneId)}' LIMIT 1
  `);

    const rows = result.toArray();
    if (rows.length === 0) {
        return null;
    }

    try {
        return JSON.parse(rows[0].polygon_json as string);
    } catch {
        return null;
    }
}

/**
 * Batch retrieve multiple polygons
 */
export async function getPolygons(zoneIds: string[]): Promise<Map<string, number[][]>> {
    const conn = await initSpatialDb();
    const results = new Map<string, number[][]>();

    if (zoneIds.length === 0) {
        return results;
    }

    const idList = zoneIds.map(id => `'${sanitizeSqlLiteral(id)}'`).join(',');
    const result = await conn.query(`
    SELECT zone_id, polygon_json FROM dggs_polygons WHERE zone_id IN (${idList})
  `);

    for (const row of result.toArray()) {
        try {
            const polygon = JSON.parse(row.polygon_json as string);
            results.set(row.zone_id as string, polygon);
        } catch {
            // Skip invalid entries
        }
    }

    return results;
}

/**
 * Batch store multiple polygons
 */
export async function storePolygons(
    polygons: Map<string, number[][]>,
    refinement: number = 3
): Promise<void> {
    const conn = await initSpatialDb();

    if (polygons.size === 0) {
        return;
    }

    // Build batch insert
    const values: string[] = [];
    for (const [zoneId, polygon] of polygons) {
        const coordinates = polygon.map(p => `${p[0]} ${p[1]}`).join(', ');
        const wkt = `POLYGON((${coordinates}))`;
        const json = JSON.stringify(polygon);
        values.push(`('${sanitizeSqlLiteral(zoneId)}', ${refinement}, '${sanitizeSqlLiteral(wkt)}', '${sanitizeSqlLiteral(json)}')`);
    }

    // Insert in batches of 100
    for (let i = 0; i < values.length; i += 100) {
        const batch = values.slice(i, i + 100);
        await conn.query(`
      INSERT INTO dggs_polygons (zone_id, refinement, polygon_wkt, polygon_json)
      VALUES ${batch.join(', ')}
      ON CONFLICT (zone_id) DO UPDATE SET
        refinement = EXCLUDED.refinement,
        polygon_wkt = EXCLUDED.polygon_wkt,
        polygon_json = EXCLUDED.polygon_json
    `);
    }
}

/**
 * Get count of cached polygons
 */
export async function getPolygonCount(): Promise<number> {
    const conn = await initSpatialDb();
    const result = await conn.query(`SELECT COUNT(*) as count FROM dggs_polygons`);
    const rows = result.toArray();
    return rows.length > 0 ? Number(rows[0].count) : 0;
}

/**
 * Clear all cached polygons
 */
export async function clearPolygonCache(): Promise<void> {
    const conn = await initSpatialDb();
    await conn.query(`DELETE FROM dggs_polygons`);
    console.log('[SpatialDB] Polygon cache cleared');
}

/**
 * Check if spatial extension is available
 */
export function isSpatialAvailable(): boolean {
    return spatialLoaded;
}

/**
 * Execute a spatial query (if spatial extension is loaded)
 */
export async function spatialQuery(sql: string): Promise<unknown[]> {
    if (!spatialLoaded) {
        throw new Error('Spatial extension not loaded');
    }
    const conn = await initSpatialDb();
    const result = await conn.query(sql);
    return result.toArray();
}

export default {
    initSpatialDb,
    storePolygon,
    getPolygon,
    getPolygons,
    storePolygons,
    getPolygonCount,
    clearPolygonCache,
    isSpatialAvailable,
    spatialQuery,
};
