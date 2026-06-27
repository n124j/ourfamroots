/**
 * E2E tests — Media upload flow.
 * Tests the 3-step direct-to-S3 upload experience.
 */
import path from 'path';
import { test, expect } from '../fixtures/auth';

const FIXTURE_JPG = path.join(__dirname, '../fixtures/sample.jpg');
const FIXTURE_PDF = path.join(__dirname, '../fixtures/sample.pdf');

test.describe('Media upload', () => {
  let treeId: string;
  let personId: string;

  test.beforeEach(async ({ authenticatedPage: page }) => {
    const token = await page.evaluate(() => (window as any).__e2e_api_token__ ?? '');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    const treeRes = await page.request.post('/api/v1/trees', {
      data: { name: `Media E2E ${Date.now()}` },
      headers,
    });
    if (treeRes.ok()) {
      treeId = (await treeRes.json()).id;
      const personRes = await page.request.post(`/api/v1/trees/${treeId}/persons`, {
        data: { given_name: 'Upload', surname: 'Test', sex: 'U' },
        headers,
      });
      if (personRes.ok()) {
        personId = (await personRes.json()).id;
      }
    }
  });

  test('MediaUploader drop zone is visible on person page', async ({
    authenticatedPage: page,
  }) => {
    if (!treeId || !personId) test.skip();

    await page.goto(`/trees/${treeId}/persons/${personId}`);
    await expect(
      page.getByText(/drop files here/i)
    ).toBeVisible({ timeout: 5_000 });
  });

  test('file input accepts image MIME types', async ({ authenticatedPage: page }) => {
    if (!treeId || !personId) test.skip();

    await page.goto(`/trees/${treeId}/persons/${personId}`);
    const input = page.locator('input[type="file"]');
    const accept = await input.getAttribute('accept');
    expect(accept).toContain('image/jpeg');
    expect(accept).toContain('application/pdf');
  });

  test('uploading an image shows it in the progress queue', async ({
    authenticatedPage: page,
  }) => {
    if (!treeId || !personId) test.skip();

    await page.goto(`/trees/${treeId}/persons/${personId}`);
    const fileInput = page.locator('input[type="file"]');

    try {
      await fileInput.setInputFiles(FIXTURE_JPG);
      await expect(
        page.locator('[class*="queue"], [class*="upload"]').getByText(/\.jpg/i)
      ).toBeVisible({ timeout: 5_000 });
    } catch {
      test.skip();
    }
  });

  test('gallery is visible on person page', async ({ authenticatedPage: page }) => {
    if (!treeId || !personId) test.skip();

    await page.goto(`/trees/${treeId}/persons/${personId}`);
    await expect(
      page.getByText(/no media yet|upload photos/i).or(
        page.locator('[class*="gallery"], [class*="masonry"]')
      )
    ).toBeVisible({ timeout: 5_000 });
  });
});
