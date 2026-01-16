import { z } from 'zod';
import { query } from '../db.js';
const createSchema = z.object({
    name: z.string().min(1),
    description: z.string().optional(),
    level: z.number().int().optional(),
    dggsName: z.string().optional(),
});
const lookupSchema = z.object({
    dggids: z.array(z.string().min(1)).min(1).max(3000),
    key: z.string().min(1).optional(),
    tid: z.number().int().optional(),
});
export const datasetRoutes = async (app) => {
    app.get('/api/datasets', async (request) => {
        const search = typeof request.query === 'object' ? request.query.search : undefined;
        if (search) {
            const result = await query('SELECT id, name, description, dggs_name, level, status, metadata, created_at FROM datasets WHERE name ILIKE $1 ORDER BY created_at DESC', [`%${search}%`]);
            return { datasets: result.rows };
        }
        const result = await query('SELECT id, name, description, dggs_name, level, status, metadata, created_at FROM datasets ORDER BY created_at DESC');
        return { datasets: result.rows };
    });
    app.post('/api/datasets', { preValidation: [app.authenticate] }, async (request, reply) => {
        const body = createSchema.safeParse(request.body);
        if (!body.success) {
            return reply.code(400).send({ error: 'Invalid request', details: body.error.flatten() });
        }
        const user = request.user;
        const { name, description, level, dggsName } = body.data;
        const result = await query('INSERT INTO datasets (name, description, level, dggs_name, created_by) VALUES ($1, $2, $3, $4, $5) RETURNING id, name, description, dggs_name, level, status, created_at', [name, description ?? null, level ?? null, dggsName ?? 'IVEA3H', user.sub]);
        return reply.code(201).send({ dataset: result.rows[0] });
    });
    app.get('/api/datasets/:id', async (request, reply) => {
        const params = request.params;
        const result = await query('SELECT id, name, description, dggs_name, level, status, metadata, created_at FROM datasets WHERE id = $1', [params.id]);
        if (result.rowCount === 0) {
            return reply.code(404).send({ error: 'Dataset not found' });
        }
        return { dataset: result.rows[0] };
    });
    app.get('/api/datasets/:id/cells', async (request) => {
        const params = request.params;
        const queryParams = request.query;
        const limit = Math.min(Number(queryParams.limit ?? 500), 5000);
        const offset = Number(queryParams.offset ?? 0);
        const values = [params.id];
        const clauses = ['dataset_id = $1'];
        let idx = 2;
        if (queryParams.key) {
            clauses.push(`attr_key = $${idx}`);
            values.push(queryParams.key);
            idx += 1;
        }
        if (queryParams.dggidPrefix) {
            clauses.push(`dggid LIKE $${idx}`);
            values.push(`${queryParams.dggidPrefix}%`);
            idx += 1;
        }
        if (queryParams.tid) {
            clauses.push(`tid = $${idx}`);
            values.push(Number(queryParams.tid));
            idx += 1;
        }
        values.push(limit, offset);
        const result = await query(`SELECT dggid, tid, attr_key, value_text, value_num, value_json FROM cell_objects
       WHERE ${clauses.join(' AND ')}
       ORDER BY dggid
       LIMIT $${idx} OFFSET $${idx + 1}`, values);
        return { cells: result.rows };
    });
    app.post('/api/datasets/:id/lookup', { preValidation: [app.authenticate] }, async (request, reply) => {
        const params = request.params;
        const body = lookupSchema.safeParse(request.body);
        if (!body.success) {
            return reply.code(400).send({ error: 'Invalid request', details: body.error.flatten() });
        }
        const { dggids, key, tid } = body.data;
        const values = [params.id, dggids];
        const clauses = ['dataset_id = $1', 'dggid = ANY($2)'];
        let idx = 3;
        if (key) {
            clauses.push(`attr_key = $${idx}`);
            values.push(key);
            idx += 1;
        }
        if (tid !== undefined) {
            clauses.push(`tid = $${idx}`);
            values.push(tid);
            idx += 1;
        }
        const result = await query(`SELECT dggid, tid, attr_key, value_text, value_num, value_json FROM cell_objects
       WHERE ${clauses.join(' AND ')}
       ORDER BY dggid`, values);
        return { cells: result.rows };
    });
};
