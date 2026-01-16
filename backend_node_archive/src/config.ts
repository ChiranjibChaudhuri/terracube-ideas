import dotenv from 'dotenv';

dotenv.config();

const port = Number(process.env.PORT ?? 4000);

export const config = {
  port,
  dbUrl: process.env.DATABASE_URL ?? '',
  jwtSecret: process.env.JWT_SECRET ?? 'change-me',
  corsOrigin: process.env.CORS_ORIGIN ?? 'http://localhost:5173',
  redis: {
    host: process.env.REDIS_HOST ?? 'localhost',
    port: Number(process.env.REDIS_PORT ?? 6379),
  },
  minio: {
    endPoint: process.env.MINIO_ENDPOINT ?? 'localhost',
    port: Number(process.env.MINIO_PORT ?? 9000),
    useSSL: false,
    accessKey: process.env.MINIO_ACCESS_KEY ?? 'minioadmin',
    secretKey: process.env.MINIO_SECRET_KEY ?? 'minioadmin',
    bucket: process.env.MINIO_BUCKET ?? 'ideas-staging',
  },
  gebco: {
    path: process.env.GEBCO_PATH ?? '',
    url: process.env.GEBCO_URL ?? '',
    minLevel: process.env.GEBCO_MIN_LEVEL ? Number(process.env.GEBCO_MIN_LEVEL) : undefined,
    maxLevel: process.env.GEBCO_MAX_LEVEL ? Number(process.env.GEBCO_MAX_LEVEL) : undefined,
    maxZonesPerLevel: process.env.GEBCO_MAX_ZONES_PER_LEVEL ? Number(process.env.GEBCO_MAX_ZONES_PER_LEVEL) : 200000,
    maxImagePixels: process.env.GEBCO_MAX_IMAGE_PIXELS ? Number(process.env.GEBCO_MAX_IMAGE_PIXELS) : 8000000,
  },
  admin: {
    email: process.env.ADMIN_EMAIL ?? 'admin@terracube.geo',
    password: process.env.ADMIN_PASSWORD ?? 'admin123',
    name: process.env.ADMIN_NAME ?? 'System Admin',
  },
};

if (!config.dbUrl) {
  console.warn('DATABASE_URL is not set. Backend will not connect to Postgres.');
}
