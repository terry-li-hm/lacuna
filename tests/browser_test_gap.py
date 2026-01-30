import asyncio
from playwright.async_api import async_playwright
import os

async def test_ui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()
        
        # Open the local frontend file
        file_path = "file://" + os.path.abspath("frontend/index.html")
        print(f"Opening {file_path}")
        await page.goto(file_path)
        
        # Set API Base
        print("Setting API base to http://localhost:8000")
        await page.fill("#apiBaseInput", "http://localhost:8000")
        await page.click("#saveApiBaseBtn")
        
        # Wait for status update
        await asyncio.sleep(2)
        status = await page.inner_text("#apiStatus")
        print(f"API Status: {status}")
        
        # Check if Gap Analysis section is present
        gap_h2 = await page.query_selector("h2:has-text('Gap Analysis')")
        if gap_h2:
            print("✅ Gap Analysis section found in UI")
        else:
            print("❌ Gap Analysis section NOT found")
            await browser.close()
            return

        # Upload a document to have something to select
        print("Uploading test document...")
        await page.set_input_files("#document", "data/documents/sample_hkma_capital.txt")
        await page.select_option("#jurisdiction", "Hong Kong")
        await page.click("#uploadBtn")
        
        # Wait for upload completion
        await page.wait_for_selector(".status.success", timeout=15000)
        print("✅ Document uploaded successfully")
        
        # Update selectors
        await asyncio.sleep(1)
        
        # Try running Gap Analysis
        print("Selecting documents for Gap Analysis...")
        # Force a refresh of selectors
        await page.evaluate("updateGapSelectors()")
        await asyncio.sleep(2)
        
        # Check if options are present
        options_count = await page.eval_on_selector("#gapCircular", "el => el.options.length")
        print(f"Gap Circular options count: {options_count}")
        
        await page.wait_for_selector("#gapCircular option:not([value=''])", state="attached", timeout=10000)
        circular_val = await page.eval_on_selector("#gapCircular option:not([value=''])", "el => el.value")
        print(f"Selected circular ID: {circular_val}")
        
        await page.select_option("#gapCircular", circular_val)
        await page.select_option("#gapBaseline", circular_val) # Compare with self for test
        
        print("Running Gap Analysis...")
        # Clear results content first to avoid seeing old upload results
        await page.evaluate("document.getElementById('resultsContent').innerHTML = ''")
        await page.click("#gapBtn")
        
        # Wait for results with specific header
        await page.wait_for_selector("h3:has-text('Gap Analysis Report')", timeout=20000)
        print("✅ Gap Analysis results displayed")
        
        # Check summary
        summary_text = await page.inner_text("#resultsContent")
        print(f"Results Content: {summary_text[:100]}...")
        if "Gap Analysis Report" in summary_text:
            print("✅ Gap Analysis Report content verified")
        else:
            print("❌ Gap Analysis Report content mismatch")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ui())
