import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { query } from './db.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const initDb = async () => {
    try {
        const schemaPath = path.resolve(__dirname, '../db/schema.sql');
        const schemaSql = await fs.readFile(schemaPath, 'utf8');

        // Run the schema SQL
        // Splitting by simple regex if needed, or trusting pg to handle multiple statements (it usually does)
        await query(schemaSql);
        console.log('Database schema initialized.');
    } catch (err) {
        console.error('Failed to initialize database schema:', err);
        throw err;
    }
};
