/* DVSwitch M17 dashboard layout v1.1.3
 * Created: 2026-11-10T21:35:00-05:00 by KE2HNI
 * Updated: 2026-11-10T22:25:00-05:00 by KE2HNI — replace cards on live refresh and restore status-panel frames.
 * Updated: 2026-11-11T12:35:00-05:00 by KE2HNI — preserve card panels and disconnect the observer while repositioning refreshed tables.
 * Updated: 2026-11-11T13:10:00-05:00 by KE2HNI — place the left card stack in the status sidebar below Analog Bridge and TRX.
 * Updated: 2026-11-11T13:25:00-05:00 by KE2HNI — place M17 Net in the right column to balance the sidebar card stack.
 * Updated: 2026-11-11T13:45:00-05:00 by KE2HNI — center activity, match activity widths, and inset side cards from the page border.
 * Updated: 2026-11-11T14:00:00-05:00 by KE2HNI — equalize activity-to-card gaps and align right-card outer insets.
 * Updated: 2026-11-11T14:10:00-05:00 by KE2HNI — lower the right card stack by 20 pixels to align with the left status cards.
 * Updated: 2026-11-11T14:20:00-05:00 by KE2HNI — add one pixel to the right stack offset and give Local Activity more separation.
 * Updated: 2026-11-11T14:30:00-05:00 by KE2HNI — keep Analog Bridge labels on one line while preserving equal outer card insets.
 * Updated: 2026-11-11T14:50:00-05:00 by KE2HNI — make both side card columns equal width so the activity panels center between them.
 * Updated: 2026-11-11T15:00:00-05:00 by KE2HNI — correct measured 10-pixel outer inset mismatch and preserve equal inner gaps.
 * Updated: 2026-11-11T16:05:00-05:00 by KE2HNI — relabel the existing RX control as M17 RX Monitor only while M17 is selected.
 * Keeps the eight network cards ordered around centered activity without flicker or duplicate panels.
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
    var center = document.createElement('div');
    center.id = 'dvs-gateway-activity';
    var right = document.createElement('div');
    right.className = 'dvs-network-cards dvs-network-cards-right';
    right.setAttribute('aria-label', 'Network status, right column including M17');
    layout.append(center, right);
    center.appendChild(activity);
    var localActivity = document.getElementById('localTxs');
    if (localActivity) {
      var oldLocalCenter = localActivity.parentElement;
      center.appendChild(localActivity);
      if (oldLocalCenter && oldLocalCenter.tagName === 'CENTER' && !oldLocalCenter.children.length) oldLocalCenter.remove();
    }
    oldCenter.parentNode.replaceChild(layout, oldCenter);

    var style = document.createElement('style');
    style.id = 'dvs-m17-network-layout-style';
    style.textContent = [
      '#dvs-network-layout{display:grid;grid-template-columns:minmax(0,1fr) 192px;align-items:start;gap:10px;width:100%;box-sizing:border-box}',
      '#dvs-gateway-activity{grid-column:1;min-width:0;width:calc(100% - 4px);justify-self:start;display:flex;flex-direction:column;align-items:center}#dvs-gateway-activity #lastHerd,#dvs-gateway-activity #localTxs{width:100%;max-width:100%;box-sizing:border-box}#dvs-gateway-activity #localTxs{margin-top:8px}#dvs-gateway-activity #lastHerd fieldset,#dvs-gateway-activity #localTxs fieldset{width:100%!important;box-sizing:border-box;margin-left:0!important;margin-right:0!important}',
      '#dvs-network-sidebar-cards{width:calc(100% - 24px);box-sizing:border-box;margin:8px 0 0 24px}',
      '.dvs-network-cards{min-width:0;text-align:center}',
      '.dvs-network-cards-right{position:relative;left:10px;padding:21px 32px 0 0;box-sizing:border-box}',
      '.nav #modeInfo>fieldset{margin-left:24px!important;width:calc(100% - 24px)!important;box-sizing:border-box}',
      '.nav #modeInfo>fieldset table th:first-child{white-space:nowrap}',
      '.dvs-network-card-panel{background-color:#e8e8e8e8;width:100%;box-sizing:border-box;margin:6px 0 8px;padding:4px;font-size:12px;border-radius:10px}',
      '.dvs-network-card-panel table{width:100%;table-layout:fixed;margin:0}',
      '.dvs-network-card-panel th,.dvs-network-card-panel td{overflow-wrap:anywhere;word-break:normal}',
      'body.theme-dark .dvs-network-cards *,body.theme-auto.dvs-prefers-dark .dvs-network-cards *{border-color:#374151!important}',
      '@media(max-width:1100px){#dvs-network-layout{grid-template-columns:minmax(0,1fr)}#dvs-gateway-activity{grid-column:1;grid-row:1;width:100%}.dvs-network-cards-right{grid-column:1;grid-row:2;left:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:0 8px;padding:0}}',
      '@media(max-width:650px){.dvs-network-cards-right{grid-template-columns:repeat(2,minmax(0,1fr))}}'
    ].join('');
    document.head.appendChild(style);
  }

  function ensureSidebarCards(info) {
    var host = document.getElementById('dvs-network-sidebar-cards');
    if (!host) {
      host = document.createElement('div');
      host.id = 'dvs-network-sidebar-cards';
      host.className = 'dvs-network-cards dvs-network-cards-left';
      host.setAttribute('aria-label', 'Network status, first three alphabetically');
      info.parentNode.insertBefore(host, info.nextSibling);
    }
    return host;
  }

  function placeCards() {
    if (moving) return;
    var info = document.getElementById('modeInfo');
    var layout = document.getElementById('dvs-network-layout');
    if (!info || !layout) return;
    var right = document.querySelector('#dvs-network-layout .dvs-network-cards-right');
    var left = ensureSidebarCards(info);
    if (!left || !right) return;

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
      var target = index < 3 && card.name !== 'M17 Net' ? left : right;
      var panel = Array.from(document.querySelectorAll('.dvs-network-card-panel')).find(function (item) {
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
    if (observer) observer.observe(info, { childList: true, subtree: true });
    moving = false;
  }

  function updateRxMonitorLabel() {
    var rx = Array.from(document.querySelectorAll('button')).find(function (button) {
      return /(?:M17 )?RX Monitor/.test(button.textContent.replace(/\s+/g, ' ').trim());
    });
    if (!rx) return;
    var shared = document.querySelector('#dvs-mode-buttons [data-mode="M17"], #dvs-asl-mode-buttons [data-mode="M17"]');
    var standalone = document.querySelector('#dvs-m17-standalone .dvs-m17-mode');
    var selected = (shared && shared.classList.contains('selected')) || (standalone && standalone.classList.contains('selected'));
    var walker = document.createTreeWalker(rx, NodeFilter.SHOW_TEXT);
    var text;
    while ((text = walker.nextNode())) {
      if (!/(?:M17 )?RX Monitor/.test(text.nodeValue)) continue;
      text.nodeValue = text.nodeValue.replace(/(?:M17 )?RX Monitor/, selected ? 'M17 RX Monitor' : 'RX Monitor');
      break;
    }
  }

  function start() {
    makeLayout();
    placeCards();
    updateRxMonitorLabel();
    var info = document.getElementById('modeInfo');
    if (info && !info.dataset.dvsM17LayoutObserved) {
      observer = new MutationObserver(placeCards);
      observer.observe(info, { childList: true, subtree: true });
      info.dataset.dvsM17LayoutObserved = '1';
    }
    ['dvs-mode-buttons', 'dvs-asl-mode-buttons', 'dvs-m17-standalone'].forEach(function (id) {
      var controls = document.getElementById(id);
      if (!controls || controls.dataset.dvsM17RxObserved) return;
      new MutationObserver(updateRxMonitorLabel).observe(controls, { attributes: true, childList: true, subtree: true, attributeFilter: ['class'] });
      controls.dataset.dvsM17RxObserved = '1';
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
  window.addEventListener('resize', function () {
    placeCards();
  });
})();
