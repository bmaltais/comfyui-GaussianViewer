const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  try {
    await page.goto('http://localhost:3000/viewer_gaussian_v2.html');

    // Check if Auto-Refine button exists
    const autoRefineBtn = await page.$('#autoRefine');
    if (autoRefineBtn) {
      console.log('✓ Auto-Refine button found');
    } else {
      console.error('✗ Auto-Refine button NOT found');
      process.exit(1);
    }

    // Check if refineStatus span exists
    const refineStatus = await page.$('#refineStatus');
    if (refineStatus) {
      console.log('✓ Refine status element found');
    } else {
      console.error('✗ Refine status element NOT found');
      process.exit(1);
    }

    // Click button without mesh/overlay - should show error
    await autoRefineBtn.click();

    // Wait for error message
    await page.waitForTimeout(500);
    const statusText = await page.innerText('#refineStatus');
    console.log('Status text after click:', statusText);

    if (statusText.includes('Error')) {
      console.log('✓ Correct error behavior (no overlay)');
    } else {
      console.warn('! Unexpected status text:', statusText);
    }

    await page.screenshot({ path: 'viewer_verification.png' });
    console.log('Screenshot saved as viewer_verification.png');

  } catch (err) {
    console.error('Error during verification:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
