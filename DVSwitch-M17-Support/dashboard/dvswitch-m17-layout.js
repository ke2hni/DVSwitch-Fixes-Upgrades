/* DVSwitch M17 dashboard layout v1.0.3
 * Created: 2026-11-10T21:35:00-05:00 by KE2HNI
 * Updated: 2026-11-11T00:50:00-05:00 by KE2HNI — make card rendering idempotent across status refreshes and cache-bust upgrades.
 * Keeps the eight network cards alphabetized without accumulating old copies.
 */
(function () {
  'use strict';
  if (window.__dvsM17LayoutInstalled) return;
  window.__dvsM17LayoutInstalled = '1.0.3';
  var cardNames = new Set(['ASL Net', 'DMR TGIF Master', 'D-Star Net', 'M17 Net', 'NXDN Net', 'P25 Net', 'STFU Net', 'YSF Net']);
  var moving = false;
  var renderTimer = null;

  function makeLayout() {
    var activity = document.getElementById('lastHerd');
    if (!activity || document.getElementById('dvs-network-layout')) return;
    var oldCenter = activity.parentElement;
    if (!oldCenter || !oldCenter.parentNode) return;

    var layout = document.createElement('div');
    layout.id = 'dvs-network-layout';
    var center = document.createElement('div');
    center.id = 'dvs-gateway-activity';
    var right = document.createElement('div');
    right.className = 'dvs-network-cards dvs-network-cards-right';
    right.setAttribute('aria-label', 'Network status, last four alphabetically');
    layout.append(center, right);
    center.appendChild(activity);
    oldCenter.parentNode.replaceChild(layout, oldCenter);

    var style = document.createElement('style');
    style.id = 'dvs-m17-network-layout-style';
    style.textContent = [
      '#dvs-network-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(180px,220px);align-items:start;gap:12px;width:100%;box-sizing:border-box}',
      '#dvs-gateway-activity{min-width:0}#dvs-gateway-activity #lastHerd{width:100%}',
      '.dvs-network-cards{min-width:0;text-align:center}',
      '.dvs-network-card-panel{background-color:#e8e8e8e8;width:100%;box-sizing:border-box;margin:6px 0 8px;padding:4px;font-size:12px;border:1px solid #8795a8;border-radius:10px;box-shadow:0 0 10px #999}',
      '.dvs-network-card-panel table{width:100%;table-layout:fixed;margin:0}',
      '.dvs-network-card-panel th,.dvs-network-card-panel td{overflow-wrap:anywhere;word-break:normal}',
      'body.theme-dark .dvs-network-cards *,body.theme-auto.dvs-prefers-dark .dvs-network-cards *,body.theme-dark #dvs-modeInfo-network-cards *,body.theme-auto.dvs-prefers-dark #dvs-modeInfo-network-cards *{border-color:#374151!important}',
      '#dvs-modeInfo-network-cards{display:block;margin-top:3px}',
      '@media(max-width:1100px){#dvs-network-layout{grid-template-columns:minmax(0,1fr)}.dvs-network-cards-right{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:0 8px}}',
      '@media(max-width:650px){.dvs-network-cards-right{grid-template-columns:repeat(2,minmax(0,1fr))}}'
    ].join('');
    document.head.appendChild(style);
  }

  function renderCards() {
    if (moving) return;
    var info = document.getElementById('modeInfo');
    var layout = document.getElementById('dvs-network-layout');
    var right = document.querySelector('#dvs-network-layout .dvs-network-cards-right');
    if (!info || !layout || !right) return;

    var cards = Array.from(info.querySelectorAll('table, .dvs-network-cards-right table')).map(function (table) {
      var heading = table.querySelector('th');
      return { table: table, name: heading ? heading.textContent.replace(/\s+/g, ' ').trim() : '' };
    }).filter(function (card) {
      return cardNames.has(card.name) || /^DMR\s+.+\s+Master$/i.test(card.name);
    });

    if (cards.length) {
      moving = true;
      // Collapse duplicate/stale rendered tables by name, keeping the latest copy.
      var unique = new Map();
      cards.forEach(function (card) {
        var key = card.name.toLocaleLowerCase('en');
        if (!unique.has(key) || card.table.closest('#modeInfo')) unique.set(key, card);
      });
      cards = Array.from(unique.values()).sort(function (a, b) { return a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }); });
      var selectedTables = new Set(cards.map(function (card) { return card.table; }));
      Array.from(info.querySelectorAll('table')).forEach(function (table) {
        var heading = table.querySelector('th');
        var name = heading ? heading.textContent.replace(/\s+/g, ' ').trim() : '';
        if ((cardNames.has(name) || /^DMR\s+.+\s+Master$/i.test(name)) && !selectedTables.has(table)) {
          var panel = table.closest('.dvs-network-card-panel');
          (panel || table).remove();
        }
      });
      // status.php refresh replaces the contents each second; detach the current
      // card tables, remove their old wrappers, then render exactly one copy.
      var leftCards = document.createElement('div');
      leftCards.id = 'dvs-modeInfo-network-cards';
      leftCards.setAttribute('aria-label', 'Network status, first four alphabetically');
      var priorLeft = info.querySelector('#dvs-modeInfo-network-cards');
      if (priorLeft) priorLeft.remove();
      right.replaceChildren();
      var trxTable = Array.from(info.querySelectorAll('table')).find(function (table) {
        if (table.closest('.dvs-network-card-panel')) return false;
        var heading = table.querySelector('th');
        return heading && heading.textContent.replace(/\s+/g, ' ').trim() === 'TRX Info';
      });
      if (trxTable) trxTable.insertAdjacentElement('afterend', leftCards);
      else info.appendChild(leftCards);
      cards.forEach(function (card, index) {
        var previous = card.table.previousElementSibling;
        if (previous && previous.tagName === 'BR') previous.remove();
        card.table.style.width = '100%';
        card.table.style.tableLayout = 'fixed';
        var panel = document.createElement('fieldset');
        panel.className = 'dvs-network-card-panel';
        panel.appendChild(card.table);
        (index < 4 ? leftCards : right).appendChild(panel);
      });
      moving = false;
    }
  }

  function placeCards() {
    if (renderTimer) window.clearTimeout(renderTimer);
    // Wait until the 1-second jQuery status refresh has finished inserting its tables.
    renderTimer = window.setTimeout(renderCards, 60);
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
  window.addEventListener('resize', function () {
    var info = document.getElementById('modeInfo');
    var layout = document.getElementById('dvs-network-layout');
    if (info && layout) placeCards();
  });
})();
