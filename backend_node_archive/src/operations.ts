import { z } from 'zod';

const base = {
  datasetId: z.string().uuid(),
  limit: z.number().int().positive().max(5000).optional(),
  offset: z.number().int().nonnegative().optional(),
};

export const operationSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('filter'),
    datasetId: base.datasetId,
    key: z.string().min(1),
    op: z.enum(['eq', 'lt', 'gt', 'lte', 'gte']),
    value: z.union([z.string(), z.number()]),
    limit: base.limit,
    offset: base.offset,
  }),
  z.object({
    type: z.literal('range'),
    datasetId: base.datasetId,
    key: z.string().min(1),
    min: z.number().optional(),
    max: z.number().optional(),
    limit: base.limit,
    offset: base.offset,
  }),
  z.object({
    type: z.literal('aggregate'),
    datasetId: base.datasetId,
    key: z.string().min(1),
    agg: z.enum(['avg', 'sum', 'min', 'max']),
    groupBy: z.enum(['dggid', 'tid']),
    limit: base.limit,
    offset: base.offset,
  }),
  z.object({
    type: z.literal('dggid-prefix'),
    datasetId: base.datasetId,
    prefix: z.string().min(1),
    limit: base.limit,
    offset: base.offset,
  }),
]);

export type Operation = z.infer<typeof operationSchema>;

const opToSql = (op: 'eq' | 'lt' | 'gt' | 'lte' | 'gte') => {
  switch (op) {
    case 'eq':
      return '=';
    case 'lt':
      return '<';
    case 'gt':
      return '>';
    case 'lte':
      return '<=';
    case 'gte':
      return '>=';
    default:
      return '=';
  }
};

export const compileOperation = (op: Operation) => {
  const limit = op.limit ?? 500;
  const offset = op.offset ?? 0;

  if (op.type === 'filter') {
    const isNumber = typeof op.value === 'number';
    const column = isNumber ? 'value_num' : 'value_text';
    const sqlOp = opToSql(op.op);
    return {
      text: `SELECT dggid, tid, attr_key, value_text, value_num, value_json FROM cell_objects
             WHERE dataset_id = $1 AND attr_key = $2 AND ${column} ${sqlOp} $3
             ORDER BY dggid
             LIMIT $4 OFFSET $5`,
      values: [op.datasetId, op.key, op.value, limit, offset],
    };
  }

  if (op.type === 'range') {
    const clauses: string[] = ['dataset_id = $1', 'attr_key = $2', 'value_num IS NOT NULL'];
    const values: unknown[] = [op.datasetId, op.key];
    let idx = values.length + 1;
    if (op.min !== undefined) {
      clauses.push(`value_num >= $${idx}`);
      values.push(op.min);
      idx += 1;
    }
    if (op.max !== undefined) {
      clauses.push(`value_num <= $${idx}`);
      values.push(op.max);
      idx += 1;
    }
    values.push(limit, offset);
    return {
      text: `SELECT dggid, tid, attr_key, value_num FROM cell_objects
             WHERE ${clauses.join(' AND ')}
             ORDER BY dggid
             LIMIT $${idx} OFFSET $${idx + 1}`,
      values,
    };
  }

  if (op.type === 'aggregate') {
    return {
      text: `SELECT ${op.groupBy}, ${op.agg}(value_num) AS value
             FROM cell_objects
             WHERE dataset_id = $1 AND attr_key = $2 AND value_num IS NOT NULL
             GROUP BY ${op.groupBy}
             ORDER BY ${op.groupBy}
             LIMIT $3 OFFSET $4`,
      values: [op.datasetId, op.key, limit, offset],
    };
  }

  return {
    text: `SELECT dggid, tid, attr_key, value_text, value_num, value_json FROM cell_objects
           WHERE dataset_id = $1 AND dggid LIKE $2
           ORDER BY dggid
           LIMIT $3 OFFSET $4`,
    values: [op.datasetId, `${op.prefix}%`, limit, offset],
  };
};
