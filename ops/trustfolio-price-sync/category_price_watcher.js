/* TrustFolio category price watcher. Reuses the existing backend CategoryService.
   No marketplace API calls. Mongo change streams are the primary trigger. */
'use strict';
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
const mongoose = require('mongoose');
const connectDB = require('../config/mongo');
const CategoryService = require('../services/CategoryService');
const { extractPriceFromString } = require('../utils/priceUtils');

const FULL = '*';
const pending = new Set();
let timer = null;
let running = false;
let stream = null;
let reconnect = null;
let streamOnline = false;
let stopped = false;

function log(event, detail = '') {
  console.log(new Date().toISOString(), event, String(detail));
}

function enqueue(slug) {
  if (slug === FULL || !slug) { pending.clear(); pending.add(FULL); }
  else if (!pending.has(FULL)) pending.add(String(slug));
  if (!timer) timer = setTimeout(() => {
    timer = null;
    void flush();
  }, 6500);
}

async function flush() {
  if (running || stopped) return;
  running = true;
  try {
    while (pending.size && !stopped) {
      const selected = [...pending];
      pending.clear();
      if (selected.includes(FULL) || selected.length >= 15) {
        const result = await CategoryService.updateAllCategoryPriceRanges();
        const failed = Object.values(result).filter(x => !x).length;
        log('CATEGORY_RANGE_FULL_REFRESH', 'categories=' + Object.keys(result).length + ',failed=' + failed);
      } else {
        for (const slug of selected) {
          try {
            const updated = await CategoryService.updateCategoryPriceRange(slug);
            log('CATEGORY_RANGE_REFRESH', slug + ',updated=' + Boolean(updated));
          } catch (e) { log('CATEGORY_RANGE_ERROR', slug + ':' + e.name); }
        }
      }
    }
  } catch (e) {
    log('PRICE_SYNC_ERROR', e.name);
    enqueue(FULL);
  } finally { running = false; }
}

// Source of truth is my_products.price; reflect writes to legacy numeric mirrors
// onto canonical price so API ranking, category ranges and the UI agree.
function sourcePrice(change) {
  if (change.operationType !== 'update') return undefined;
  const fields = change.updateDescription?.updatedFields || {};
  if (Object.prototype.hasOwnProperty.call(fields, 'price')) return fields.price;
  for (const key of ['price_inr', 'currentPriceValue', 'current_price_value',
    'currentPrice', 'current_price']) {
    if (Object.prototype.hasOwnProperty.call(fields, key)) return fields[key];
  }
  if (Object.prototype.hasOwnProperty.call(fields, 'live.price_inr')
      || Object.prototype.hasOwnProperty.call(fields, 'live')) {
    const live = change.fullDocument?.live;
    if (live?.status === 'ok') return live.price_inr;
  }
  return undefined;
}

function relevant(change) {
  if (change.operationType !== 'update') return true;
  const fields = [
    ...Object.keys(change.updateDescription?.updatedFields || {}),
    ...(change.updateDescription?.removedFields || [])
  ];
  return fields.some(f => /^(price|price_inr|currentPrice|current_price|live|isActive|category|product_category|category_slug)/.test(f));
}

async function onProductChange(change) {
  if (!relevant(change) || stopped) return;
  const fields = change.updateDescription?.updatedFields || {};
  const removed = change.updateDescription?.removedFields || [];
  const categoryChanged = Object.keys(fields).some(k => /^(category|category_slug|product_category)$/.test(k))
    || removed.some(k => /^(category|category_slug|product_category)$/.test(k));
  const doc = change.fullDocument;
  const slug = doc?.category_slug || doc?.category || doc?.product_category;
  if (change.operationType === 'delete' || categoryChanged || !slug) {
    enqueue(FULL); // old category may be unknown after deletion/reclassification
  } else {
    enqueue(slug);
  }

  // Direct MongoDB updates to price_inr or currentPriceValue must not leave
  // canonical 'price' stale. This does not perform an external live-price fetch.
  const raw = sourcePrice(change);
  if (raw === undefined || !change.documentKey?._id || !doc) return;
  const value = extractPriceFromString(raw);
  const col = mongoose.connection.collection('my_products');
  if (Number.isFinite(value) && value > 0) {
    const normalized = String(Math.round(value * 100) / 100);
    const updates = {};
    if (String(doc.price ?? '') !== normalized) updates.price = normalized;
    if (Number(doc.price_inr) !== Number(normalized)) updates.price_inr = Number(normalized);
    if (Object.keys(updates).length) {
      await col.updateOne({ _id: change.documentKey._id }, { $set: updates });
      log('CANONICAL_PRICE_SYNC', 'fields=' + Object.keys(updates).join(','));
    }
  } else if (['price', 'price_inr', 'currentPriceValue'].some(k => Object.prototype.hasOwnProperty.call(fields, k))) {
    // An explicit non-price (null/zero/N/A) should not keep an old usable price.
    await col.updateOne(
      { _id: change.documentKey._id },
      { $unset: { price: '', price_inr: '' } }
    );
    log('CANONICAL_PRICE_INVALIDATED');
  }
}

function retryStream() {
  if (reconnect || stopped) return;
  streamOnline = false;
  reconnect = setTimeout(() => {
    reconnect = null;
    void startStream();
  }, 10000);
}

async function startStream() {
  if (stopped) return;
  try {
    if (mongoose.connection.readyState !== 1) await connectDB();
    if (stream) await stream.close().catch(() => {});
    stream = mongoose.connection.collection('my_products').watch(
      [{ $match: { operationType: { $in: ['insert', 'update', 'replace', 'delete'] } } }],
      { fullDocument: 'updateLookup', maxAwaitTimeMS: 2000 }
    );
    stream.on('change', event => {
      void onProductChange(event).catch(e => { log('CHANGE_HANDLER_ERROR', e.name); enqueue(FULL); });
    });
    stream.on('error', e => { log('CHANGE_STREAM_ERROR', e.name); retryStream(); });
    stream.on('close', () => { log('CHANGE_STREAM_CLOSED'); retryStream(); });
    streamOnline = true;
    log('CHANGE_STREAM_ACTIVE', 'my_products');
    enqueue(FULL); // reconcile changes missed during any outage
  } catch (e) {
    log('CHANGE_STREAM_START_ERROR', e.name);
    retryStream();
  }
}

async function main() {
  await connectDB();
  log('PRICE_SYNC_CONNECTED');
  await startStream();
  setInterval(() => enqueue(FULL), 15 * 60 * 1000).unref();
  // When stream is down, poll at 5-minute intervals instead.
  setInterval(() => { if (!streamOnline) enqueue(FULL); }, 5 * 60 * 1000).unref();
}
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    if (reconnect) clearTimeout(reconnect);
    void (async () => {
      if (stream) await stream.close().catch(() => {});
      await mongoose.disconnect().catch(() => {});
      process.exit(0);
    })();
  });
}
if (require.main === module) {
  main().catch(e => { log('STARTUP_FAILURE', e.name); process.exitCode = 1; });
}
module.exports = { sourcePrice, relevant };
