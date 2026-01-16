import { Pool } from 'pg';
import { config } from './config.js';
export const pool = new Pool({ connectionString: config.dbUrl });
export const query = async (text, params = []) => {
    const result = await pool.query(text, params);
    return result;
};
