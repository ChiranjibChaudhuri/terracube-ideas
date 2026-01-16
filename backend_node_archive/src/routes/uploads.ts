import { FastifyInstance } from 'fastify';
import { query } from '../db.js';
import { minio } from '../minio.js';
import { config } from '../config.js';
import { preprocessQueue } from '../queue.js';

export const uploadRoutes = async (app: FastifyInstance) => {
  app.post('/api/uploads', { preValidation: [app.authenticate] }, async (request, reply) => {
    const data = await request.file();
    if (!data) {
      return reply.code(400).send({ error: 'File is required' });
    }

    const user = request.user as { sub: string };
    const datasetIdField = (data.fields as any)?.datasetId?.value as string | undefined;
    const datasetNameField = (data.fields as any)?.datasetName?.value as string | undefined;
    const datasetDescriptionField = (data.fields as any)?.datasetDescription?.value as string | undefined;
    const attrKeyField = (data.fields as any)?.attrKey?.value as string | undefined;
    const minLevelField = (data.fields as any)?.minLevel?.value as string | undefined;
    const maxLevelField = (data.fields as any)?.maxLevel?.value as string | undefined;
    const sourceTypeField = (data.fields as any)?.sourceType?.value as string | undefined;
    let datasetId = datasetIdField;

    if (!datasetId) {
      const datasetName = datasetNameField ?? `Upload ${new Date().toISOString()}`;
      const created = await query<{ id: string }>(
        'INSERT INTO datasets (name, description, created_by, status) VALUES ($1, $2, $3, $4) RETURNING id',
        [datasetName, datasetDescriptionField ?? null, user.sub, 'staged']
      );
      datasetId = created.rows[0].id;
      const metadata: Record<string, unknown> = {};
      if (attrKeyField) metadata.attr_key = attrKeyField;
      if (minLevelField) metadata.min_level = Number(minLevelField);
      if (maxLevelField) metadata.max_level = Number(maxLevelField);
      if (sourceTypeField) metadata.source_type = sourceTypeField;
      if (Object.keys(metadata).length) {
        await query('UPDATE datasets SET metadata = $1 WHERE id = $2', [metadata, datasetId]);
      }
    } else if (attrKeyField || minLevelField || maxLevelField || sourceTypeField) {
      const current = await query<{ metadata: Record<string, unknown> }>(
        'SELECT metadata FROM datasets WHERE id = $1',
        [datasetId]
      );
      const metadata = current.rows[0]?.metadata ?? {};
      if (attrKeyField && !metadata.attr_key) metadata.attr_key = attrKeyField;
      if (minLevelField && !metadata.min_level) metadata.min_level = Number(minLevelField);
      if (maxLevelField && !metadata.max_level) metadata.max_level = Number(maxLevelField);
      if (sourceTypeField && !metadata.source_type) metadata.source_type = sourceTypeField;
      await query('UPDATE datasets SET metadata = $1 WHERE id = $2', [metadata, datasetId]);
    }

    const safeName = data.filename.replace(/[^a-zA-Z0-9._-]/g, '_');
    const storageKey = `${datasetId}/${Date.now()}-${safeName}`;

    const buffer = await data.toBuffer();

    await minio.putObject(
      config.minio.bucket,
      storageKey,
      buffer,
      buffer.length,
      data.mimetype ? { 'Content-Type': data.mimetype } : undefined
    );

    const uploadResult = await query<{ id: string }>(
      'INSERT INTO uploads (dataset_id, filename, mime_type, size_bytes, storage_key, status) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id',
      [datasetId, data.filename, data.mimetype ?? null, buffer.length, storageKey, 'staged']
    );

    const uploadId = uploadResult.rows[0].id;

    await preprocessQueue.add('preprocess', {
      uploadId,
      datasetId,
      storageKey,
      filename: data.filename,
      mimeType: data.mimetype ?? 'application/octet-stream',
      attrKey: attrKeyField,
      minLevel: minLevelField ? Number(minLevelField) : undefined,
      maxLevel: maxLevelField ? Number(maxLevelField) : undefined,
      sourceType: sourceTypeField,
    });

    return reply.code(201).send({ uploadId, datasetId });
  });

  app.get('/api/uploads', { preValidation: [app.authenticate] }, async () => {
    const result = await query(
      'SELECT id, dataset_id, filename, mime_type, size_bytes, storage_key, status, error, created_at, updated_at FROM uploads ORDER BY created_at DESC'
    );
    return { uploads: result.rows };
  });
};
