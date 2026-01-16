import { Pool, QueryResultRow } from 'pg';
import { config } from './config.js';

export const pool = new Pool({ connectionString: config.dbUrl });

export const query = async <T extends QueryResultRow>(text: string, params: unknown[] = []) => {
  const result = await pool.query<T>(text, params as any[]);
  return result;
};
