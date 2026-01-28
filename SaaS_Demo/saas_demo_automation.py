import asyncio
import os
import time
from playwright.async_api import async_playwright

# Configuration
BASE_URL = "http://localhost:8080"
ADMIN_EMAIL = "admin@terracube.xyz"
ADMIN_PASSWORD = "ChangeThisSecurePassword123!"
OUTPUT_DIR = "outputs"
VIDEO_DIR = "videos"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

async def run_demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir=VIDEO_DIR,
            record_video_size={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        print("Scene 1: Landing Page")
        await page.goto(BASE_URL)
        await asyncio.sleep(4)
        await page.evaluate("window.scrollTo({top: 800, behavior: 'smooth'})")
        await asyncio.sleep(4)
        await page.screenshot(path=f"{OUTPUT_DIR}/1_landing_page.png")

        print("Scene 2: Login")
        await page.click("a.button-primary:has-text('Launch Dashboard'), a.button-secondary:has-text('Sign In')")
        await page.wait_for_selector("input#email")
        await page.fill("input#email", ADMIN_EMAIL)
        await page.fill("input#password", ADMIN_PASSWORD)
        await page.click("button.button-primary:has-text('Sign in')")
        
        await page.wait_for_url(f"{BASE_URL}/dashboard")
        await asyncio.sleep(6) 
        await page.screenshot(path=f"{OUTPUT_DIR}/2_dashboard_id.png")

        print("Scene 3: 3D Globe")
        await page.get_by_text("Map Settings").scroll_into_view_if_needed()
        if await page.query_selector("text=3D Globe View") is None:
            await page.get_by_text("Map Settings").click()
        
        await page.click("text=3D Globe View") 
        await asyncio.sleep(8)
        await page.screenshot(path=f"{OUTPUT_DIR}/3_dashboard_globe.png")

        print("Scene 4: Adding Global Data")
        if await page.query_selector(".dataset-search__input") is None:
             await page.get_by_text("Add Layer").click()
        
        # Check if already loaded
        if await page.query_selector(".layer-item") is None:
            await page.fill(".dataset-search__input", "Global")
            await asyncio.sleep(4)
            await page.click(".dataset-search__item:has-text('Global')")
            await asyncio.sleep(8)
        else:
            print("Layer already present, skipping add.")
            
        await page.screenshot(path=f"{OUTPUT_DIR}/4_data_loaded.png")

        print("Scene 5: Styling & Visual Analysis")
        if await page.query_selector(".toolbox-tabs") is None:
            await page.get_by_text("Toolbox").click()
            
        await page.click(".toolbox-tab:has-text('Style')") 
        await asyncio.sleep(2)
        
        ramps = ["plasma", "magma", "temperature", "elevation", "bathymetry"]
        for ramp in ramps:
            print(f"  Applying {ramp} ramp...")
            await page.locator("select.toolbox-select").nth(1).select_option(ramp)
            await page.click("button.toolbox-button:has-text('Apply Style')")
            await asyncio.sleep(4)
            await page.screenshot(path=f"{OUTPUT_DIR}/5_styling_{ramp}.png")
        
        print("Scene 6: Multi-Scale Resolution Control")
        if await page.query_selector("text=Resolution Mode") is None:
             await page.get_by_text("Map Settings").click()
             
        await page.select_option("select.toolbox-select:near(label:has-text('Resolution Mode'))", "fixed")
        await asyncio.sleep(3)
        
        for level in [2, 4, 6, 8]:
            print(f"  Setting Resolution Level {level}...")
            await page.evaluate(f"(val) => {{ const slider = document.querySelector('.toolbox-range'); if(slider) {{ slider.value = val; slider.dispatchEvent(new Event('input', {{ bubbles: true }})); slider.dispatchEvent(new Event('change', {{ bubbles: true }})); }} }}", level)
            await asyncio.sleep(6) 
            await page.mouse.wheel(0, -400) 
            await asyncio.sleep(4)
            await page.screenshot(path=f"{OUTPUT_DIR}/6_resolution_level_{level}.png")

        print("Scene 7: Spatial Buffer")
        # Click the TOOLS tab very specifically
        await page.click(".toolbox-tab:has-text('Tools')")
        await asyncio.sleep(3)
        
        # Explicit wait for the palette
        await page.wait_for_selector(".tool-palette-item", state="visible")
        await page.click(".tool-palette-item:has-text('Buffer')")
        
        # Wait for modal
        await page.wait_for_selector(".tool-modal", state="visible")
        await asyncio.sleep(2)
        await page.click("button.toolbox-button:has-text('Run Operation')")
        
        print("  Waiting for operation completion...")
        await page.wait_for_selector(".toolbox-status:has-text('Operation complete')", timeout=120000)
        await asyncio.sleep(6)
        await page.screenshot(path=f"{OUTPUT_DIR}/7_buffer_result.png")

        print("Scene 8: Analyst Workbench")
        await page.goto(f"{BASE_URL}/workbench")
        await asyncio.sleep(15) 
        await page.screenshot(path=f"{OUTPUT_DIR}/8_analyst_workbench.png")

        print("Scene 9: Sign Out")
        await page.goto(f"{BASE_URL}/dashboard")
        await asyncio.sleep(4)
        await page.get_by_text("Sign out").click()
        await asyncio.sleep(4)
        print("Demo completed successfully.")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_demo())
