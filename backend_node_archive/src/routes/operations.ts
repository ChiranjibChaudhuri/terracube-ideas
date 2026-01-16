import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { compileOperation, operationSchema } from '../operations.js';
import { query } from '../db.js';

const spatialSchema = z.object({
  type: z.enum(['intersection', 'zonal']),
  datasetAId: z.string().uuid(),
  datasetBId: z.string().uuid(),
  keyA: z.string().min(1),
  keyB: z.string().min(1).optional(),
  tid: z.number().int().optional(),
  limit: z.number().int().positive().max(5000).optional(),
});

const toRange = (metadata: Record<string, unknown>) => {
  const min = metadata.min_level !== undefined ? Number(metadata.min_level) : undefined;
  const max = metadata.max_level !== undefined ? Number(metadata.max_level) : undefined;
  return { min, max };
};

const rangesOverlap = (a: { min?: number; max?: number }, b: { min?: number; max?: number }) => {
  if (a.min === undefined || a.max === undefined || b.min === undefined || b.max === undefined) {
    return false;
  }
  return Math.max(a.min, b.min) <= Math.min(a.max, b.max);
};

export const operationRoutes = async (app: FastifyInstance) => {
  app.post('/api/ops/query', { preValidation: [app.authenticate] }, async (request, reply) => {
    const parsed = operationSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: 'Invalid operation', details: parsed.error.flatten() });
    }
    const { text, values } = compileOperation(parsed.data);
    const result = await query(text, values);
    return { rows: result.rows };
  });

  app.post('/api/ops/spatial', { preValidation: [app.authenticate] }, async (request, reply) => {
    const parsed = spatialSchema.safeParse(request.body);
    if (!parsed.success) {
      return reply.code(400).send({ error: 'Invalid operation', details: parsed.error.flatten() });
    }

    const { datasetAId, datasetBId, keyA, keyB, tid, type } = parsed.data;
    const limit = parsed.data.limit ?? 1000;

    const datasets = await query<{ id: string; metadata: Record<string, unknown> }>(
      'SELECT id, metadata FROM datasets WHERE id = ANY($1)',
      [[datasetAId, datasetBId]]
    );

    const datasetA = datasets.rows.find((row) => row.id === datasetAId);
    const datasetB = datasets.rows.find((row) => row.id === datasetBId);

    if (!datasetA || !datasetB) {
      return reply.code(404).send({ error: 'Dataset not found' });
    }

    const rangeA = toRange(datasetA.metadata ?? {});
    const rangeB = toRange(datasetB.metadata ?? {});

    if (!rangesOverlap(rangeA, rangeB)) {
      return reply.code(409).send({
        error: 'Resolution mismatch',
        details: 'Datasets must have overlapping min/max DGGS levels to run spatial operations.',
      });
    }

    if (type === 'intersection') {
      const values: unknown[] = [datasetAId, datasetBId, keyA];
      const clauses = ['a.dataset_id = $1', 'b.dataset_id = $2', 'a.dggid = b.dggid', 'a.attr_key = $3'];
      let idx = 4;
      if (keyB) {
        clauses.push(`b.attr_key = $${idx}`);
        values.push(keyB);
        idx += 1;
      }
      if (tid !== undefined) {
        clauses.push(`a.tid = $${idx}`);
        values.push(tid);
        idx += 1;
      }
      values.push(limit);

      const result = await query(
        `SELECT a.dggid, a.value_num AS value_num, a.value_text AS value_text, b.value_num AS value_num_b, b.value_text AS value_text_b
         FROM cell_objects a
         JOIN cell_objects b ON a.dggid = b.dggid
         WHERE ${clauses.join(' AND ')}
         LIMIT $${idx}`,
        values
      );
      return { rows: result.rows, operation: 'intersection' };
    }

    const values: unknown[] = [datasetAId, datasetBId, keyA];
    const clauses = ['a.dataset_id = $1', 'b.dataset_id = $2', 'a.attr_key = $3', 'a.dggid = b.dggid'];
    let idx = 4;
    if (tid !== undefined) {
      clauses.push(`a.tid = $${idx}`);
      values.push(tid);
      idx += 1;
    }
    values.push(limit);

    const result = await query(
      `SELECT b.dggid AS dggid, AVG(a.value_num) AS value_num
       FROM cell_objects a
       JOIN cell_objects b ON a.dggid = b.dggid
       WHERE ${clauses.join(' AND ')}
       GROUP BY b.dggid
       LIMIT $${idx}`,
      values
    );
    return { rows: result.rows, operation: 'zonal' };
  });
};
