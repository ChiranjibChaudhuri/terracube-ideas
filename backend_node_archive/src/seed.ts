import { query } from './db.js';
import { hashPassword } from './auth.js';
import { config } from './config.js';

export const seedAdmin = async () => {
    const { email, password, name } = config.admin;

    try {
        const existing = await query('SELECT id FROM users WHERE email = $1', [email]);
        if ((existing.rowCount ?? 0) > 0) {
            console.log('Admin account already exists.');
            return;
        }

        const passwordHash = await hashPassword(password);
        await query(
            'INSERT INTO users (email, password_hash, name) VALUES ($1, $2, $3)',
            [email, passwordHash, name]
        );
        console.log(`Admin account created: ${email}`);
    } catch (error) {
        console.error('Failed to seed admin account:', error);
    }
};
