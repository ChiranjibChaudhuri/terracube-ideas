import { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { query } from '../db.js';
import { hashPassword, verifyPassword } from '../auth.js';

const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  name: z.string().min(1).optional(),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

export const authRoutes = async (app: FastifyInstance) => {
  app.post('/api/auth/register', async (request, reply) => {
    const body = registerSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ error: 'Invalid request', details: body.error.flatten() });
    }
    const { email, password, name } = body.data;
    const existing = await query('SELECT id FROM users WHERE email = $1', [email]);
    if ((existing.rowCount ?? 0) > 0) {
      return reply.code(409).send({ error: 'Email already registered' });
    }
    const passwordHash = await hashPassword(password);
    const result = await query<{ id: string }>(
      'INSERT INTO users (email, password_hash, name) VALUES ($1, $2, $3) RETURNING id',
      [email, passwordHash, name ?? null]
    );
    const userId = result.rows[0].id;
    const token = app.jwt.sign({ sub: userId, email });
    return reply.send({ token, user: { id: userId, email, name: name ?? null } });
  });

  app.post('/api/auth/login', async (request, reply) => {
    const body = loginSchema.safeParse(request.body);
    if (!body.success) {
      return reply.code(400).send({ error: 'Invalid request', details: body.error.flatten() });
    }
    const { email, password } = body.data;
    const result = await query<{ id: string; password_hash: string; name: string | null }>(
      'SELECT id, password_hash, name FROM users WHERE email = $1',
      [email]
    );
    if (result.rowCount === 0) {
      return reply.code(401).send({ error: 'Invalid credentials' });
    }
    const user = result.rows[0];
    const ok = await verifyPassword(password, user.password_hash);
    if (!ok) {
      return reply.code(401).send({ error: 'Invalid credentials' });
    }
    const token = app.jwt.sign({ sub: user.id, email });
    return reply.send({ token, user: { id: user.id, email, name: user.name } });
  });

  app.get('/api/me', { preValidation: [app.authenticate] }, async (request) => {
    const user = request.user as { sub: string; email: string };
    const result = await query<{ id: string; email: string; name: string | null }>(
      'SELECT id, email, name FROM users WHERE id = $1',
      [user.sub]
    );
    if (result.rowCount === 0) {
      return { user: null };
    }
    return { user: result.rows[0] };
  });
};
