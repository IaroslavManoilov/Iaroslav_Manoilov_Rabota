"""Local Chrome/CDP CMS reader. Product requests are GET only; never prints tokens."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]

# Authentication stays inside the browser. Only catalog data crosses this boundary.
READ_SCRIPT = r"""async ({base, sku, maxPages}) => {
  async function request(path, options = {}) {
    const response = await fetch(base + path, {
      ...options, credentials: 'include', cache: 'no-store',
      signal: AbortSignal.timeout(30000)
    });
    if (!response.ok) throw Error('CMS HTTP ' + response.status);
    return await response.json();
  }
  const auth = await request('/auth/v1/auth/refresh', {method: 'POST'});
  if (typeof auth.accessToken !== 'string' || !auth.accessToken)
    throw Error('CMS accessToken missing; sign in manually');
  const headers = {Authorization: 'Bearer ' + auth.accessToken};
  const get = path => request(path, {headers});
  const attributes = await get('/commerce/v1/admin/attributes/all');
  const categories = await get('/commerce/v1/admin/categories');
  if (!sku) return {health: 'authenticated_catalog_read_ok', attributes, categories};
  const normalize = value => String(value ?? '').trim().toUpperCase();
  const wanted = normalize(sku);
  const seen = new Map();
  const matches = new Map();
  const readOne = async id => {
    const key = String(id);
    if (!seen.has(key)) {
      const product = await get('/commerce/v1/admin/products/' + encodeURIComponent(key));
      if (!product || String(product.id) !== key)
        throw Error('Unexpected product detail shape or ID');
      seen.set(key, product);
    }
    return seen.get(key);
  };
  let exhausted = false;
  for (let page = 1; page <= maxPages; page++) {
    const result = await get('/commerce/v1/admin/products?perPage=100&page=' + page
      + '&filter%5Bsearch%5D=' + encodeURIComponent(sku));
    const items = result?.data?.items ?? result?.items;
    if (!Array.isArray(items)) throw Error('Unexpected search response shape');
    if (items.length === 0) { exhausted = true; break; }
    for (const candidate of items) {
      if (candidate.id == null) throw Error('Search candidate has no ID');
      const product = await readOne(candidate.id);
      if (normalize(product.sku) === wanted) matches.set(String(product.id), product);
      if (product.type === 'variable' || Array.isArray(product.variants)) {
        for (const child of product.variants ?? []) {
          if (child.id == null) throw Error('Variant has no ID');
          const full = await readOne(child.id);
          if (normalize(full.sku) === wanted) matches.set(String(full.id), full);
        }
      }
    }
  }
  if (!exhausted) throw Error('Pagination limit reached; lookup incomplete');
  if (matches.size === 0) throw Error('Exact SKU not found in searched CMS results');
  if (matches.size !== 1) throw Error('Multiple exact SKU matches; resolve ambiguity');
  const product = [...matches.values()][0];
  const family = new Map([[String(product.id), product]]);
  let parent = null;
  if (product.parent_id != null) parent = await readOne(product.parent_id);
  else if (product.type === 'variable') parent = product;
  if (parent) {
    if (!Array.isArray(parent.variants)) throw Error('Parent variants missing');
    family.set(String(parent.id), parent);
    for (const child of parent.variants) {
      if (child.id == null) throw Error('Variant has no ID');
      const full = await readOne(child.id);
      if (String(full.parent_id) !== String(parent.id))
        throw Error('Variant parent mismatch');
      family.set(String(full.id), full);
    }
    if (product.parent_id != null && !parent.variants.some(x => String(x.id) === String(product.id)))
      throw Error('Requested variant missing from parent list');
  }
  return {product, family: [...family.values()], attributes, categories,
    lookup: {exact: true, pagination_exhausted: exhausted}};
}"""


def load_config() -> dict:
    path = ROOT / 'config' / 'workspace.local.json'
    if not path.exists():
        path = ROOT / 'config' / 'workspace.example.json'
    config = json.loads(path.read_text(encoding='utf-8'))
    cdp = urlsplit(config['cdp_url'])
    if cdp.scheme != 'http' or cdp.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('CDP must use local HTTP loopback')
    if config['api_base'].rstrip('/') != 'https://api.vitra.md':
        raise ValueError('This reader only supports the verified ViTRA API host')
    if urlsplit(config['admin_url']).hostname != 'admin.vitra.md':
        raise ValueError('This reader only supports admin.vitra.md')
    return config


def safe_sku_path(sku: str) -> str:
    cleaned = ''.join(c if c.isascii() and (c.isalnum() or c in '-_') else '_' for c in sku)
    return cleaned[:90] or 'sku'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--health', action='store_true')
    mode.add_argument('--sku')
    parser.add_argument('--max-pages', type=int, default=100)
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error('--max-pages must be positive')
    sku = args.sku.strip() if args.sku else ''
    if args.sku is not None and not sku:
        parser.error('SKU must not be empty')
    config = load_config()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(config['cdp_url'])
        pages = [page for context in browser.contexts for page in context.pages
                 if urlsplit(page.url).hostname == 'admin.vitra.md']
        if not pages:
            raise RuntimeError('Admin tab missing in dedicated Chrome')
        # Do not close an attached user browser.
        result = pages[0].evaluate(READ_SCRIPT, {
            'base': config['api_base'].rstrip('/'), 'sku': sku, 'maxPages': args.max_pages
        })

    if args.health:
        print(json.dumps({'health': result['health'], 'product_writes': False}))
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder = ROOT / 'styles' / 'work' / 'product_runs' / f'{stamp}_{safe_sku_path(sku)}'
    folder.mkdir(parents=True, exist_ok=False)
    snapshot = folder / 'before.json'
    snapshot.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'sku': result['product']['sku'], 'id': result['product']['id'],
        'type': result['product'].get('type'), 'family_members': len(result['family']),
        'snapshot': snapshot.relative_to(ROOT).as_posix(), 'product_writes': False
    }, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never emit browser response bodies, access tokens, cookies, or full tracebacks.
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__,
                          'action': 'Check local Chrome, CMS login and response schema; see docs/MAC-SETUP.md'}))
        raise SystemExit(1)
