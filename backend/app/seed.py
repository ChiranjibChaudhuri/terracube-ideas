import asyncio
import logging
from app.db import get_db_pool, close_db_pool
from app.auth import get_password_hash
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_admin():
    """
    Seed the admin user account.
    The pool is NOT closed here when called from main.py - lifecycle is managed by the application.
    """
    email = settings.ADMIN_EMAIL
    password = settings.ADMIN_PASSWORD
    name = settings.ADMIN_NAME

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
            if existing:
                await conn.execute(
                    """
                    UPDATE users
                    SET role = 'admin',
                        is_active = TRUE,
                        name = COALESCE(name, $2)
                    WHERE email = $1
                    """,
                    email,
                    name,
                )
                logger.info("Admin account already exists. Ensured admin role is applied.")
                return

            password_hash = get_password_hash(password)
            await conn.execute(
                """
                INSERT INTO users (email, password_hash, name, role, is_active)
                VALUES ($1, $2, $3, 'admin', TRUE)
                """,
                email,
                password_hash,
                name,
            )
            logger.info(f"Admin account created: {email}")
    except Exception as e:
        logger.error(f"Failed to seed admin: {e}")


if __name__ == "__main__":
    async def run():
        await seed_admin()
        await close_db_pool()
    
    asyncio.run(run())
