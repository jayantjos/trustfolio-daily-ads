'use strict';

/**
 * Product-specific store availability decisions. Do not mistake gateway/WAF/API
 * failures for a permanently unavailable item.
 *
 * For safety, missing Croma search results ("no_price") are NOT product not-found.
 */
const PERMANENT = new Set([
  'out_of_stock','outofstock','sold_out','soldout','discontinued',
  'permanently_unavailable','item_sold_out','item_discontinued',
  'product_discontinued','no_longer_available'
]);
const AMBIGUOUS = new Set([
  'not_available','unavailable','n/a','na','not_found','not_listed',
  'page_not_found','item_not_available','temporarily_unavailable',
  'http_404','http_410','404','410'
]);
const TRANSIENT = new Set([
  'error','store_error','blocked','timeout','timed_out','skipped','no_price',
  'http_502','http_503','http_504','502','503','504','gateway_timeout',
  'bad_gateway','fetch_failed','network_error','page_load_failed'
]);
const normalize = value => String(value ?? '').trim().toLowerCase()
  .replace(/[\s-]+/g,'_').replace(/_+/g,'_');
const rawText = value => String(value ?? '').trim().toLowerCase();
const permanentRegex = /\b(discontinued|sold\s*out|out\s*of\s*stock|no\s*longer\s*available|permanently\s*unavailable)\b/i;
const ambiguousRegex = /(?:^|[\s:])(?:n\/a|not\s+available|unavailable|not\s+listed|product\s+not\s+found|item\s+not\s+found)(?:$|[\s.!:])/i;
const errorRegex = /\b(502|503|504|gateway|server\s+error|request\s+failed|timed?\s*out|captcha|access\s+denied|blocked)\b/i;

function classify(result) {
  if (!result || typeof result !== 'object') return 'transient';
  const status=normalize(result.status);
  const statusRaw=rawText(result.status);
  const availability=rawText(result.availability);
  const availabilityStatus=normalize(result.availability);
  const detail=rawText(result.error);
  const http=Number(result.http_status ?? result.httpStatus ?? result.statusCode ?? 0);
  if (http >= 500 || (http >= 400 && http !== 404 && http !== 410) ||
      errorRegex.test(detail)) return 'transient';
  // A transport error cannot assert product availability, even with a stale label.
  if (status !== 'no_price' && TRANSIENT.has(status)) return 'transient';
  if (PERMANENT.has(status) || PERMANENT.has(availabilityStatus) || permanentRegex.test(statusRaw) || permanentRegex.test(availability))
    return 'permanent';
  if (AMBIGUOUS.has(status) || AMBIGUOUS.has(availabilityStatus) || ambiguousRegex.test(statusRaw) ||
      ambiguousRegex.test(availability) || http===404 || http===410)
    return 'ambiguous';
  return TRANSIENT.has(status) ? 'transient' : 'none';
}
function toAvailabilityState(result,previous={},now=new Date()) {
  const kind=classify(result);
  const oldKind=classify(previous);
  const checks = kind==='ambiguous' ? (oldKind==='ambiguous' ?
    (Number(previous.unavailable_checks)||0)+1 : 1)
    : kind==='permanent' ? (Number(previous.unavailable_checks)||0)+1 : 0;
  return {
    unavailable_checks:checks,
    availability_signal:kind,
    availability_since:kind==='ambiguous' && oldKind==='ambiguous' && previous.availability_since
      ? previous.availability_since : kind==='ambiguous' || kind==='permanent' ? now : null
  };
}
function isConfirmedUnavailable(live) {
  if (!live) return false;
  const kind=classify(live);
  return kind==='permanent' || (kind==='ambiguous' && (Number(live.unavailable_checks)||0)>=2);
}

module.exports={classify,toAvailabilityState,isConfirmedUnavailable};
