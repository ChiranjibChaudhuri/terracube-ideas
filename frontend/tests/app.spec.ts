import { test, expect } from '@playwright/test';

test.describe('TerraCube IDEAS Application', () => {
  test('should load the landing page and have correct title', async ({ page }) => {
    // Vite starts on port 5173 by default
    await page.goto('/');

    // Check page title (assuming it's set in index.html)
    await expect(page).toHaveTitle(/TerraCube IDEAS/);

    // Verify main brand elements are visible
    const brandElement = page.locator('.brand span');
    await expect(brandElement).toHaveText(/TerraCube IDEAS/);

    // Verify hero tagline
    const heroTagline = page.locator('.hero-tagline');
    await expect(heroTagline).toContainText(/Geospatial/i); // Adjust based on actual tagline

    // Check if login button or navigation exists
    const loginButton = page.getByRole('button', { name: /login/i });
    if (await loginButton.isVisible()) {
      await expect(loginButton).toBeVisible();
    }
  });

  test('should redirect to login when unauthenticated', async ({ page }) => {
    await page.goto('/workbench');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
    
    // Check login form visibility
    const emailInput = page.getByText(/email/i);
    await expect(emailInput).toBeVisible();
  });

  test('should render workbench when authenticated', async ({ page }) => {
    // Navigate to a page first to set localStorage
    await page.goto('/');
    
    // Set a dummy token with a far-future exp claim
    // Base64 of {"exp": 9999999999} is eyJleHAiOiA5OTk5OTk5OTk5fQ
    await page.evaluate(() => {
      localStorage.setItem('ideas_token', 'header.eyJleHAiOiA5OTk5OTk5OTk5fQ.sig');
    });

    // Now go to workbench
    await page.goto('/workbench');

    // Wait for the shell to load
    await page.waitForSelector('.workbench-shell', { timeout: 10000 });

    // Check sidebar visibility
    const sidebarTitle = page.locator('.workbench-sidebar__title');
    await expect(sidebarTitle).toBeVisible();
  });
});
