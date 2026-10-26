// Offline contract checks only. These do not authenticate or contact ViTRA.
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../styles/work/cms_read.py', import.meta.url), 'utf8');
const script = source.match(/READ_SCRIPT = r"""([\s\S]*?)"""/)[1];
const readCatalog = (0, eval)(`(${script})`);
const base = 'https://api.vitra.md';

function mockApi({ pages = [[]], products = {}, authStatus = 200 }) {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    const path = new URL(url).pathname;
    calls.push({ path, method: options.method ?? 'GET' });
    let value;
    let status = 200;
    if (path === '/auth/v1/auth/refresh') {
      value = { accessToken: 'OFFLINE_TEST_TOKEN' };
      status = authStatus;
    } else if (path.endsWith('/attributes/all') || path.endsWith('/categories')) value = [];
    else if (path === '/commerce/v1/admin/products') {
      const page = Number(new URL(url).searchParams.get('page'));
      value = { data: { items: pages[page - 1] ?? [] } };
    } else {
      value = products[path.split('/').at(-1)];
      if (!value) status = 404;
    }
    return { ok: status >= 200 && status < 300, status, json: async () => value };
  };
  return calls;
}

test('health never returns the access token and never writes products', async () => {
  const calls = mockApi({});
  const result = await readCatalog({ base, sku: '', maxPages: 5 });
  assert.equal(result.health, 'authenticated_catalog_read_ok');
  assert.equal(JSON.stringify(result).includes('OFFLINE_TEST_TOKEN'), false);
  assert.ok(calls.every(x => x.method === 'GET' || x.path === '/auth/v1/auth/refresh'));
});

test('rejects a fuzzy SKU even if it is the only search result', async () => {
  mockApi({ pages: [[{ id: 1 }], []], products: { 1: { id: 1, sku: 'ABC-bundle', type: 'simple' } } });
  await assert.rejects(readCatalog({ base, sku: 'ABC', maxPages: 5 }), /Exact SKU not found/);
});

test('paginates, resolves exact hidden child and hydrates full family', async () => {
  const calls = mockApi({ pages: [[{ id: 9 }], [{ id: 1 }], []], products: {
    9: { id: 9, sku: 'OTHER', type: 'simple' },
    1: { id: 1, sku: 'PARENT', type: 'variable', variants: [{ id: 2 }, { id: 3 }] },
    2: { id: 2, sku: 'ABC', type: 'variant', parent_id: 1 },
    3: { id: 3, sku: 'DEF', type: 'variant', parent_id: 1 }
  } });
  const result = await readCatalog({ base, sku: 'abc', maxPages: 5 });
  assert.equal(result.product.id, 2);
  assert.equal(result.family.length, 3);
  assert.equal(result.lookup.pagination_exhausted, true);
  assert.ok(calls.every(x => x.method === 'GET' || x.path === '/auth/v1/auth/refresh'));
});

test('rejects duplicate exact SKU IDs', async () => {
  mockApi({ pages: [[{ id: 1 }, { id: 2 }], []], products: {
    1: { id: 1, sku: 'ABC' }, 2: { id: 2, sku: 'ABC' }
  } });
  await assert.rejects(readCatalog({ base, sku: 'ABC', maxPages: 5 }), /Multiple exact/);
});

test('does not treat incomplete pagination as not found', async () => {
  mockApi({ pages: [[{ id: 1 }]], products: { 1: { id: 1, sku: 'ABC' } } });
  await assert.rejects(readCatalog({ base, sku: 'ABC', maxPages: 1 }), /Pagination limit/);
});

test('stops on authorization failure', async () => {
  const calls = mockApi({ authStatus: 401 });
  await assert.rejects(readCatalog({ base, sku: 'ABC', maxPages: 5 }), /CMS HTTP 401/);
  assert.equal(calls.length, 1);
});

test('rejects a child with an inconsistent parent link', async () => {
  mockApi({ pages: [[{ id: 1 }], []], products: {
    1: { id: 1, sku: 'PARENT', type: 'variable', variants: [{ id: 2 }] },
    2: { id: 2, sku: 'ABC', type: 'variant', parent_id: 77 },
    77: { id: 77, sku: 'WRONG_PARENT', type: 'variable', variants: [] }
  } });
  await assert.rejects(readCatalog({ base, sku: 'ABC', maxPages: 5 }), /missing from parent list/);
});
