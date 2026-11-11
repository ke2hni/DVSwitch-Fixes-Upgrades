/* DVSwitch M17 dashboard layout v1.0.0
 * Created: 2026-11-10T21:35:00-05:00 by KE2HNI
 * Places the eight network cards in alphabetical order on both sides of Gateway Activity.
 */
(function () {
  'use strict';
  var cardNames = new Set(['ASL Net', 'DMR TGIF Master', 'D-Star Net', 'M17 Net', 'NXDN Net', 'P25 Net', 'STFU Net', 'YSF Net']);
  var moving = false;

  function makeLayout() {
    var activity = document.getElementById('lastHerd');
    if (!activity || document.getElementById('dvs-network-layout')) return;
    var oldCenter = activity.parentElement;
    if (!oldCenter || !oldCenter.parentNode) return;
    var layout = document.createElement('div');
    layout.id = 'dvs-network-layout';
    var left = document.createElement('div');
    left.className = 'dvs-network-cards dvs-network-cards-left';
    left.setAttribute('aria-label', 'Network status, first four alphabetically');
    var center = document.createElement('div');
    center.id = 'dvs-gateway-activity';
    var right = document.createElement('div');
    right.className = 'dvs-network-cards dvs-network-cards-right';
    right.setAttribute('aria-label', 'Network status, last four alphabetically');
    layout.append(left, center, right);
    center.appendChild(activity);
    oldCenter.parentNode.replaceChild(layout, oldCenter);
    var style = document.createElement('style');
    style.id = 'dvs-m17-network-layout-style';
    style.textContent = 'body.theme-dark .dvs-network-cards *,body.theme-auto.dvs-prefers-dark .dvs-network-cards *{border-color:#374151!important}#dvs-network-layout{display:grid;grid-template-columns:minmax(138px,1fr) minmax(0,8fr) minmax(138px,1fr);align-items:start;gap:10px;width:100%;box-sizing:border-box}#dvs-gateway-activity{min-width:0}#dvs-gateway-activity #lastHerd{width:100%}.dvs-network-cards{min-width:0;text-align:center}.dvs-network-cards table{width:100%;table-layout:fixed;margin:0 0 8px}.dvs-network-cards th,.dvs-network-cards td{overflow-wrap:anywhere;word-break:normal}@media(max-width:1100px){#dvs-network-layout{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}#dvs-gateway-activity{grid-column:1/-1;grid-row:1}.dvs-network-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:0 8px}}@media(max-width:650px){#dvs-network-layout{grid-template-columns:minmax(0,1fr)}#dvs-gateway-activity{grid-column:1;grid-row:1}.dvs-network-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}';
    document.head.appendChild(style);
  }

  function placeCards() {
    if (moving) return;
    var info = document.getElementById('modeInfo');
    var left = document.querySelector('#dvs-network-layout .dvs-network-cards-left');
    var right = document.querySelector('#dvs-network-layout .dvs-network-cards-right');
    if (!info || !left || !right) return;
    moving = true;
    var cards = Array.from(info.querySelectorAll('table')).map(function (table) {
      var heading = table.querySelector('th');
      return { table: table, name: heading ? heading.textContent.replace(/\s+/g, ' ').trim() : '' };
    }).filter(function (card) { return cardNames.has(card.name) || /^DMR\s+.+\s+Master$/i.test(card.name); });
    cards.sort(function (a, b) { return a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }); });
    cards.forEach(function (card, index) {
      var previous = card.table.previousElementSibling;
      if (previous && previous.tagName === 'BR') previous.remove();
      card.table.style.width = '100%';
      card.table.style.tableLayout = 'fixed';
      (index < 4 ? left : right).appendChild(card.table);
    });
    moving = false;
  }

  function start() {
    makeLayout();
    placeCards();
    var info = document.getElementById('modeInfo');
    if (info && !info.dataset.dvsM17LayoutObserved) {
      new MutationObserver(placeCards).observe(info, { childList: true, subtree: true });
      info.dataset.dvsM17LayoutObserved = '1';
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
  window.setInterval(start, 1000);
})();
