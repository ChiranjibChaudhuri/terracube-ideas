import { Client } from 'minio';
import { config } from './config.js';
export const minio = new Client({
    endPoint: config.minio.endPoint,
    port: config.minio.port,
    useSSL: config.minio.useSSL,
    accessKey: config.minio.accessKey,
    secretKey: config.minio.secretKey,
});
export const ensureBucket = async () => {
    const bucket = config.minio.bucket;
    const exists = await minio.bucketExists(bucket).catch(() => false);
    if (!exists) {
        await minio.makeBucket(bucket, 'us-east-1');
    }
};
