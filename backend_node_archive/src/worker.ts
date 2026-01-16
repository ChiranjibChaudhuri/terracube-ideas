import { Worker } from 'bullmq';
import { config } from './config.js';
import { preprocessUpload } from './preprocess.js';

const worker = new Worker(
  'preprocess',
  async (job) => {
    await preprocessUpload(job.data);
  },
  {
    connection: {
      host: config.redis.host,
      port: config.redis.port,
    },
  }
);

worker.on('failed', (job, err) => {
  console.error('Preprocess job failed', job?.id, err);
});

console.log('Preprocess worker running');
