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

async def ensure_section_open(page, section_text, indicator_selector):
    """Ensures a sidebar section is open by checking for an indicator element."""
    print(f"  Ensuring section '{section_text}' is open...")
    indicator = await page.query_selector(indicator_selector)
    if not indicator:
        await page.get_by_text(section_text).click()
        await asyncio.sleep(3)

async def clear_all_layers(page):
    """Removes all currently active layers to ensure a clean visual state."""
    print("  Cleaning up existing layers...")
    while True:
        try:
            remove_button = await page.query_selector(".layer-item__remove")
            if not remove_button:
                break
            await remove_button.click()
            await asyncio.sleep(2) 
        except Exception as e:
            print(f"  Error removing layer: {e}")
            break

async def run_demo():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir=VIDEO_DIR,
            record_video_size={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        print("Scene 1: The Vision")
        await page.goto(BASE_URL)
        await asyncio.sleep(6)
        await page.evaluate("window.scrollTo({top: 800, behavior: 'smooth'})")
        await asyncio.sleep(6)
        await page.screenshot(path=f"{OUTPUT_DIR}/1_vision.png")

        print("Scene 2: Secure Access")
        await page.click("a.button-primary:has-text('Launch Dashboard'), a.button-secondary:has-text('Sign In')")
        await page.wait_for_selector("input#email")
        await page.fill("input#email", ADMIN_EMAIL)
        await page.fill("input#password", ADMIN_PASSWORD)
        await page.click("button.button-primary:has-text('Sign in')")
        
        await page.wait_for_url(f"{BASE_URL}/dashboard")
        await asyncio.sleep(15) 
        await page.screenshot(path=f"{OUTPUT_DIR}/2_dashboard_ready.png")

        print("Scene 3: Basemap Quality (Unified Selection)")
        await ensure_section_open(page, "Map Settings", "label:has-text('Basemap')")
        
        print("  Setting Voyager + Blue Marble HD basemap...")
        await page.select_option("select:near(label:has-text('Basemap'))", "voyager-blue-marble-hd")
        await asyncio.sleep(8)
        
        print("  Toggling 3D Globe...")
        await page.click("text=3D Globe View") 
        await asyncio.sleep(15)
        await page.screenshot(path=f"{OUTPUT_DIR}/3_basemap_quality.png")

        print("Scene 4: Dataset vs Results (Clean Separation)")
        await ensure_section_open(page, "Add Layer", ".dataset-search__tab")
             
        print("  Checking Results tab...")
        await page.click(".dataset-search__tab:has-text('Results')")
        await asyncio.sleep(6)
        await page.screenshot(path=f"{OUTPUT_DIR}/4_results_tab_empty.png")
        
        print("  Switching to Datasets tab...")
        await page.click(".dataset-search__tab:has-text('Datasets')")
        await page.fill(".dataset-search__input", "Global Temperature")
        await asyncio.sleep(6)
        await page.click(".dataset-search__item:has-text('Global Temperature')")
        
        print("  Waiting for high-resolution data load (35s)...")
        await asyncio.sleep(35) 
        await page.screenshot(path=f"{OUTPUT_DIR}/4_global_temp_added.png")

        print("Scene 5: Resolution Control (Zoom Offset)")
        await ensure_section_open(page, "Map Settings", "label:has-text('Zoom Offset')")
             
        print("  Setting Zoom Offset to +4...")
        await page.evaluate("(val) => { const sliders = document.querySelectorAll('.toolbox-range'); if(sliders.length > 0) { sliders[0].value = val; sliders[0].dispatchEvent(new Event('input', { bubbles: true })); sliders[0].dispatchEvent(new Event('change', { bubbles: true })); } }", 4)
        await asyncio.sleep(8)
        
        print("  Zooming in and waiting for resolution refinement (30s)...")
        await page.mouse.wheel(0, -1500) 
        await asyncio.sleep(30)
        await page.screenshot(path=f"{OUTPUT_DIR}/5_resolution_offset.png")

        print("Scene 6: Regional Raster Detail")
        await clear_all_layers(page)
        await ensure_section_open(page, "Add Layer", ".dataset-search__input")
        
        await page.fill(".dataset-search__input", "Dubai DEM")
        await asyncio.sleep(6)
        await page.click(".dataset-search__item:has-text('Dubai DEM')")
        
        print("  Waiting for regional high-res data (45s)...")
        await asyncio.sleep(45)
        await page.screenshot(path=f"{OUTPUT_DIR}/6_regional_raster.png")

        print("Scene 7: Vector Context Layer")
        await clear_all_layers(page)
        await ensure_section_open(page, "Add Layer", ".dataset-search__input")
        
        await page.fill(".dataset-search__input", "Canada Boundaries")
        await asyncio.sleep(6)
        await page.click(".dataset-search__item:has-text('Canada Boundaries')")
        
        print("  Waiting for vector data load (25s)...")
        await asyncio.sleep(25)
        
        await ensure_section_open(page, "Toolbox", ".toolbox-tabs")
            
        print("  Applying styling...")
        await page.click(".toolbox-tab:has-text('Style')")
        await asyncio.sleep(5)
        await page.locator("select.toolbox-select").nth(1).select_option("elevation")
        await page.evaluate("(val) => { const slider = document.querySelector('.toolbox-range'); if(slider) { slider.value = val; slider.dispatchEvent(new Event('input', { bubbles: true })); slider.dispatchEvent(new Event('change', { bubbles: true })); } }", 0.6)
        await page.click("button.toolbox-button:has-text('Apply Style')")
        await asyncio.sleep(12)
        await page.screenshot(path=f"{OUTPUT_DIR}/7_vector_context.png")

        print("Scene 8: Spatial Operation (Unary Buffer)")
        await ensure_section_open(page, "Toolbox", ".toolbox-tabs")
        await page.click(".toolbox-tab:has-text('Tools')")
        await asyncio.sleep(8)
        
        print("  Selecting Buffer tool...")
        await page.wait_for_selector(".tool-palette__tool:has-text('Buffer')", state="visible")
        await page.click(".tool-palette__tool:has-text('Buffer')")
        await page.wait_for_selector(".tool-modal", state="visible")
        await asyncio.sleep(5)
        
        await page.fill(".tool-modal__input", "2")
        await page.click("button.tool-modal__run:has-text('Run Tool')")
        
        print("  Waiting for operation completion (45s)...")
        await page.wait_for_selector(".toolbox-status:has-text('Operation complete')", timeout=150000)
        await asyncio.sleep(6)
        await page.click(".tool-modal__close")
        await asyncio.sleep(6)
        
        await ensure_section_open(page, "Add Layer", ".dataset-search__tab")
        await page.click(".dataset-search__tab:has-text('Results')")
        await asyncio.sleep(8)
        await page.click(".dataset-search__item:has-text('Buffer result')")
        print("  Waiting for result layer to load (30s)...")
        await asyncio.sleep(30)
        await page.screenshot(path=f"{OUTPUT_DIR}/8_buffer_operation.png")

        print("Scene 9: Spatial Operation (Binary Intersection)")
        await clear_all_layers(page)
        
        await ensure_section_open(page, "Add Layer", ".dataset-search__input")
        print("  Adding World Countries...")
        await page.click(".dataset-search__tab:has-text('Datasets')")
        await page.fill(".dataset-search__input", "World Countries")
        await asyncio.sleep(8)
        await page.click(".dataset-search__item:has-text('World Countries')")
        await asyncio.sleep(15)
        
        print("  Adding Canada Boundaries...")
        await page.fill(".dataset-search__input", "Canada Boundaries")
        await asyncio.sleep(8)
        await page.click(".dataset-search__item:has-text('Canada Boundaries')")
        await asyncio.sleep(15)
        
        await ensure_section_open(page, "Toolbox", ".toolbox-tabs")
        await page.click(".toolbox-tab:has-text('Tools')")
        await asyncio.sleep(6)
        await page.click(".tool-palette__tool:has-text('Intersection')")
        await page.wait_for_selector(".tool-modal", state="visible")
        await asyncio.sleep(8)
        
        await page.locator(".tool-modal__select").nth(0).select_option(label="World Countries")
        await asyncio.sleep(4)
        await page.locator(".tool-modal__select").nth(1).select_option(label="Canada Boundaries")
        await asyncio.sleep(5)
        
        await page.click("button.tool-modal__run:has-text('Run Tool')")
        await page.wait_for_selector(".toolbox-status:has-text('Operation complete')", timeout=150000)
        await asyncio.sleep(6)
        await page.click(".tool-modal__close")
        await asyncio.sleep(6)
        
        await ensure_section_open(page, "Add Layer", ".dataset-search__tab")
        await page.click(".dataset-search__tab:has-text('Results')")
        await asyncio.sleep(8)
        await page.click(".dataset-search__item:has-text('Intersection result')")
        print("  Waiting for final intersection result (45s)...")
        await asyncio.sleep(45)
        await page.screenshot(path=f"{OUTPUT_DIR}/9_intersection_operation.png")

        print("Scene 10: Wrap-Up")
        await page.click("button:has-text('Sign out')")
        await asyncio.sleep(10)
        print("Demo completed successfully.")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_demo())
