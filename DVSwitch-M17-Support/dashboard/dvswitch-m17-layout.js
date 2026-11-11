/* DVSwitch M17 dashboard layout v1.0.3
 * Created: 2026-11-10T21:35:00-05:00 by KE2HNI
 * Updated: 2026-11-10T22:25:00-05:00 by KE2HNI — replace cards on live refresh and restore status-panel frames.
 * Updated: 2026-11-11T12:35:00-05:00 by KE2HNI — preserve card panels and disconnect the observer while repositioning refreshed tables.
 * Updated: 2026-11-11T12:55:00-05:00 by KE2HNI — align the left card stack below both Analog Bridge and TRX status panels.
 * Keeps the eight network cards alphabetized around Gateway Activity without flicker or duplicate panels.
 */
(function () {
  'use strict';
  var cardNames = new Set(['ASL Net', 'DMR TGIF Master', 'D-Star Net', 'M17 Net', 'NXDN Net', 'P25 Net', 'STFU Net', 'YSF Net']);
  var moving = false;
  var observer = null;

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
    style.textContent = [
      '#dvs-network-layout{display:grid;grid-template-columns:minmax(180px,1fr) minmax(0,8fr) minmax(180px,1fr);align-items:start;gap:10px;width:100%;box-sizing:border-box}',
      '#dvs-gateway-activity{min-width:0}#dvs-gateway-activity #lastHerd{width:100%}',
      '.dvs-network-cards{min-width:0;text-align:center}',
      '.dvs-network-card-panel{background-color:#e8e8e8e8;width:100%;box-sizing:border-box;margin:6px 0 8px;padding:4px;font-size:12px;border-radius:10px}',
      '.dvs-network-card-panel table{width:100%;table-layout:fixed;margin:0}',
      '.dvs-network-card-panel th,.dvs-network-card-panel td{overflow-wrap:anywhere;word-break:normal}',
      'body.theme-dark .dvs-network-cards *,body.theme-auto.dvs-prefers-dark .dvs-network-cards *{border-color:#374151!important}',
      '@media(max-width:1100px){#dvs-network-layout{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}#dvs-gateway-activity{grid-column:1/-1;grid-row:1}.dvs-network-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:0 8px}.dvs-network-cards-left{padding-top:0!important}}',
      '@media(max-width:650px){#dvs-network-layout{grid-template-columns:minmax(0,1fr)}#dvs-gateway-activity{grid-column:1;grid-row:1}.dvs-network-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}'
    ].join('');
    document.head.appendChild(style);
  }

  function alignLeftCards(info, layout, left) {
    var statusTables = Array.from(info.querySelectorAll('table')).filter(function (table) {
      var heading = table.querySelector('th');
      return heading && /^(Analog Bridge Info|TRX Info)$/i.test(heading.textContent.replace(/\s+/g, ' ').trim());
    });
    if (!statusTables.length) return;
    var statusBottom = Math.max.apply(null, statusTables.map(function (table) {
      return table.getBoundingClientRect().bottom;
    }));
    var offset = Math.max(0, statusBottom - layout.getBoundingClientRect().top);
    left.style.paddingTop = offset + 'px';
  }

  function placeCards() {
    if (moving) return;
    var info = document.getElementById('modeInfo');
    var layout = document.getElementById('dvs-network-layout');
    var left = document.querySelector('#dvs-network-layout .dvs-network-cards-left');
    var right = document.querySelector('#dvs-network-layout .dvs-network-cards-right');
    if (!info || !layout || !left || !right) return;

    var cards = Array.from(info.querySelectorAll('table')).map(function (table) {
      var heading = table.querySelector('th');
      return { table: table, name: heading ? heading.textContent.replace(/\s+/g, ' ').trim() : '' };
    }).filter(function (card) { return cardNames.has(card.name) || /^DMR\s+.+\s+Master$/i.test(card.name); });

    if (!cards.length) return;
    moving = true;
    // Ignore mutations caused by moving dashboard tables; only the dashboard's next refresh should trigger placement.
    if (observer) observer.disconnect();
    cards.sort(function (a, b) { return a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }); });
    cards.forEach(function (card, index) {
      var target = index < 4 ? left : right;
      var panel = Array.from(layout.querySelectorAll('.dvs-network-card-panel')).find(function (item) {
        return item.dataset.cardName === card.name;
      });
      if (!panel) {
        panel = document.createElement('fieldset');
        panel.className = 'dvs-network-card-panel';
        panel.dataset.cardName = card.name;
      }
      var oldTable = panel.querySelector('table');
      if (oldTable !== card.table) {
        var previous = card.table.previousElementSibling;
        if (previous && previous.tagName === 'BR') previous.remove();
        card.table.style.width = '100%';
        card.table.style.tableLayout = 'fixed';
        if (oldTable) oldTable.replaceWith(card.table);
        else panel.appendChild(card.table);
      }
      if (panel.parentElement !== target) target.appendChild(panel);
    });
    alignLeftCards(info, layout, left);
    if (observer) observer.observe(info, { childList: true, subtree: true });
    moving = false;
  }

  function start() {
    makeLayout();
    placeCards();
    var info = document.getElementById('modeInfo');
    if (info && !info.dataset.dvsM17LayoutObserved) {
      observer = new MutationObserver(placeCards);
      observer.observe(info, { childList: true, subtree: true });
      info.dataset.dvsM17LayoutObserved = '1';
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
  window.addEventListener('resize', function () {
    var info = document.getElementById('modeInfo');
    var layout = document.getElementById('dvs-network-layout');
    var left = document.querySelector('#dvs-network-layout .dvs-network-cards-left');
    if (info && layout && left) alignLeftCards(info, layout, left);
  });
})();
