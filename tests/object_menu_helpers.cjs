'use strict';
const objectValues = page => page.locator('[data-object-value]').evaluateAll(items => items.map(item => item.dataset.objectValue));
const objectValue = page => page.locator('#object-filter').getAttribute('value');
async function selectObject(page, value) {
  await page.locator('#object-filter').click();
  const item = page.locator('[data-object-value="' + value + '"]');
  const group = await item.evaluate(element => element.closest('[data-object-submenu]').dataset.objectSubmenu);
  await page.locator('[data-object-group="' + group + '"]').click();
  await item.click();
  await page.waitForFunction(value => document.querySelector('#object-filter')?.value === value, value);
}
module.exports = { objectValues, objectValue, selectObject };
