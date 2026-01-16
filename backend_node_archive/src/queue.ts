import { Queue } from 'bullmq';
import { config } from './config.js';

export const preprocessQueue = new Queue('preprocess', {
  connection: {
    host: config.redis.host,
    port: config.redis.port,
  },
});
