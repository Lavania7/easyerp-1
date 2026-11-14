const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.EASYERP_PLAYWRIGHT_MODULE || 'playwright');

const url = process.env.EASYERP_URL || 'http://127.0.0.1:8092';
const passed = [];
const check = (name, value = true) => {
  assert.ok(value, name);
  passed.push(name);
  console.log('PASS: ' + name);
};

(async () => {
  const browser = await chromium.launch({
    headless: true,
    channel: process.env.EASYERP_BROWSER_CHANNEL || 'msedge',
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    let posts = 0;
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().includes('/api/')) posts++;
    });
    await page.goto(url + '/?mode=demo&start=2026-01-01&end=2026-12-31#/data');
    await page.waitForFunction(() => !!window.easyerpManual);
    const metadata = await page.request.get(url + '/api/entry/meta?mode=demo');
    assert.equal(metadata.status(), 200);
    const catalog = await metadata.json();
    const queued = [];
    const records = [];
    await page.route('**/api/entry/meta?**', (route) => {
      queued.push(route);
    });
    await page.route('**/api/entry/record?**', (route) => {
      records.push(route);
    });
    const waitForCount = async (items, count) => {
      const deadline = Date.now() + 5000;
      while (items.length < count && Date.now() < deadline)
        await new Promise((resolve) => setTimeout(resolve, 20));
      assert.ok(items.length >= count, 'expected pending request');
    };
    const open = async (key, id = null) => {
      await page.evaluate(
        ({ key, id }) => {
          window.easyerpManual.open(key, id);
        },
        { key, id }
      );
    };
    const close = () => page.locator('#manual-entry [data-entry-close]').first().click();
    const title = () => page.locator('#manual-entry h2').textContent();

    await open('sales.客户档案表');
    await waitForCount(queued, 1);
    await close();
    await open('rd.产品主数据表');
    await waitForCount(queued, 2);
    await queued[1].fulfill({ json: catalog });
    await page.locator('#entry-submit').waitFor();
    const productTitle = await title();
    check('latest dialog displays the requested product form', /产品/.test(productTitle));
    await queued[0].fulfill({ json: catalog });
    await page.waitForTimeout(100);
    check('late metadata cannot replace the current form', (await title()) === productTitle);
    await close();

    await open('sales.客户档案表');
    await waitForCount(queued, 3);
    await close();
    await queued[2].fulfill({ status: 503, json: { error: 'stale request failure' } });
    await page.waitForTimeout(100);
    check(
      'late errors do not reopen or alter a closed dialog',
      !(await page.locator('#manual-entry').evaluate((el) => el.open)) &&
        (await page.locator('#manual-entry .entry-error').count()) === 0
    );

    const choices = await page.request.get(
      url + '/api/entry/choices?mode=demo&object=' + encodeURIComponent('sales.客户档案表')
    );
    const customers = (await choices.json()).rows;
    assert.ok(customers.length, 'demo customer required for read-only record race');
    const id = customers[0].value;
    const saved = await page.request.get(
      url +
        '/api/entry/record?mode=demo&object=' +
        encodeURIComponent('sales.客户档案表') +
        '&id=' +
        encodeURIComponent(id)
    );
    const record = await saved.json();
    await open('sales.客户档案表', id);
    await waitForCount(queued, 4);
    await queued[3].fulfill({ json: catalog });
    await waitForCount(records, 1);
    await close();
    await open('rd.产品主数据表');
    await waitForCount(queued, 5);
    await queued[4].fulfill({ json: catalog });
    await page.locator('#entry-submit').waitFor();
    await records[0].fulfill({ json: record });
    await page.waitForTimeout(100);
    check(
      'late record data cannot overwrite a newer create form',
      (await title()) === productTitle
    );
    check(
      'the current form still accepts input',
      await page.locator('#manual-entry [data-entry-value]:not([disabled])').first().isEditable()
    );
    await close();

    check('no business writes during race tests', posts === 0);
    check('no uncaught JavaScript errors', errors.length === 0);
    fs.mkdirSync(path.join(__dirname, '../reports'), { recursive: true });
    fs.writeFileSync(
      path.join(__dirname, '../reports/manual-race-tests.json'),
      JSON.stringify({ status: 'PASS', checks: passed.length, passed }, null, 2)
    );
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
