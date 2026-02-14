"""
Integration tests for authentication and authorization.
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.config import settings


@pytest.fixture
def async_client():
    """Create an async test client."""
    return AsyncClient(app=app, base_url="http://test")


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """Test successful login returns JWT token."""
    # First, register a user
    register_response = await async_client.post(
        "/api/auth/register",
        json={
            "email": "logintest@example.com",
            "password": "testpass123",
            "name": "Login Test User"
        }
    )
    assert register_response.status_code == 200

    # Now login
    login_response = await async_client.post(
        "/api/auth/login",
        json={
            "email": "logintest@example.com",
            "password": "testpass123"
        }
    )

    assert login_response.status_code == 200
    data = login_response.json()
    assert "token" in data
    assert "user" in data
    assert data["user"]["email"] == "logintest@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    """Test login with wrong password returns 401."""
    # Register a user
    await async_client.post(
        "/api/auth/register",
        json={
            "email": "wrongpass@example.com",
            "password": "testpass123",
            "name": "Wrong Password User"
        }
    )

    # Login with wrong password
    response = await async_client.post(
        "/api/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword"
        }
    )

    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    """Test registering with duplicate email returns 409."""
    email = "duplicate@example.com"

    # First registration
    response1 = await async_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "name": "Duplicate User"
        }
    )
    assert response1.status_code == 200

    # Second registration with same email
    response2 = await async_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "name": "Duplicate User 2"
        }
    )

    assert response2.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(async_client: AsyncClient):
    """Test accessing protected endpoint without token returns 401."""
    response = await async_client.get("/api/datasets")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_info(async_client: AsyncClient):
    """Test getting current user info with valid token."""
    # Register and login
    register_resp = await async_client.post(
        "/api/auth/register",
        json={
            "email": "me@example.com",
            "password": "testpass123",
            "name": "Me User"
        }
    )

    token = register_resp.json()["token"]

    # Get user info
    response = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == "me@example.com"
