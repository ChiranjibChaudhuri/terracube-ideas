import Fastify from 'fastify';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import jwt from '@fastify/jwt';
import multipart from '@fastify/multipart';
import { config } from './config.js';
import { ensureBucket } from './minio.js';
import { authRoutes } from './routes/auth.js';
import { datasetRoutes } from './routes/datasets.js';
import { operationRoutes } from './routes/operations.js';
import { spatialRoutes } from './routes/spatial.js';
import { uploadRoutes } from './routes/uploads.js';
const app = Fastify({ logger: true });
await app.register(cors, {
    origin: config.corsOrigin,
});
await app.register(helmet);
await app.register(jwt, {
    secret: config.jwtSecret,
});
await app.register(multipart, {
    limits: {
        fileSize: 1024 * 1024 * 200,
    },
});
app.decorate('authenticate', async (request, reply) => {
    try {
        await request.jwtVerify();
    }
    catch (err) {
        reply.code(401).send({ error: 'Unauthorized' });
    }
});
app.get('/api/health', async () => ({ status: 'ok' }));
await app.register(authRoutes);
await app.register(datasetRoutes);
await app.register(operationRoutes);
await app.register(spatialRoutes);
await app.register(uploadRoutes);
const start = async () => {
    await ensureBucket();
    await app.listen({ port: config.port, host: '0.0.0.0' });
};
start().catch((err) => {
    app.log.error(err);
    process.exit(1);
});
