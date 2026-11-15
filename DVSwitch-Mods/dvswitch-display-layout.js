/* DVSwitch-Mods display layout v1.3.8
 * Created: 2026-11-15T17:35:00Z by KE2HNI
 * Generic widescreen activity and network-card layout; contains no M17 mode controls.
 */
(function () {
  'use strict';
  var cardNames = new Set(['ASL Net', 'DMR TGIF Master', 'D-Star Net', 'M17 Net', 'NXDN Net', 'P25 Net', 'STFU Net', 'YSF Net']);
  var moving = false;
  var observer = null;

  function identity(name) {
    return /^DMR\s+(?:BM|TGIF)\s+Master$/i.test(name) ? 'DMR Master' : name;
  }

  function makeLayout() {
    var activity = document.getElementById('lastHerd');
    if (!activity || document.getElementById('dvs-network-layout')) return;
    var oldCenter = activity.parentElement;
    if (!oldCenter || !oldCenter.parentNode) return;
    var aslActivity = oldCenter.querySelector('#dvs-asl-activity');
    var layout = document.createElement('div');
    layout.id = 'dvs-network-layout';
    var center = document.createElement('div');
    center.id = 'dvs-gateway-activity';
    var right = document.createElement('div');
    right.className = 'dvs-network-cards dvs-network-cards-right';
    layout.append(center, right);
    if (aslActivity) center.appendChild(aslActivity);
    center.appendChild(activity);
    var localActivity = document.getElementById('localTxs');
    if (localActivity) {
      var previousCenter = localActivity.parentElement;
      center.appendChild(localActivity);
      if (previousCenter && previousCenter.tagName === 'CENTER' && !previousCenter.children.length) previousCenter.remove();
    }
    oldCenter.parentNode.replaceChild(layout, oldCenter);
    var style = document.createElement('style');
    style.id = 'dvs-display-layout-style';
    style.textContent = [
      '#dvs-network-layout{display:grid;grid-template-columns:minmax(0,1fr) 192px;align-items:start;gap:10px;width:100%;box-sizing:border-box}',
      '#dvs-gateway-activity{grid-column:1;min-width:0;width:calc(100% - 4px);justify-self:start;display:flex;flex-direction:column;align-items:center}#dvs-gateway-activity #lastHerd,#dvs-gateway-activity #localTxs{width:100%;max-width:100%;box-sizing:border-box}#dvs-gateway-activity #localTxs{margin-top:8px}#dvs-gateway-activity #lastHerd fieldset,#dvs-gateway-activity #localTxs fieldset{width:100%!important;box-sizing:border-box;margin-left:0!important;margin-right:0!important}',
      '#dvs-network-sidebar-cards{width:calc(100% - 24px);box-sizing:border-box;margin:8px 0 0 24px}',
      '.dvs-network-cards{min-width:0;text-align:center}.dvs-network-cards-right{position:relative;left:10px;padding:21px 32px 0 0;box-sizing:border-box}',
      '.nav #modeInfo>fieldset{margin-left:24px!important;width:calc(100% - 24px)!important;box-sizing:border-box}.nav #modeInfo>fieldset table th:first-child{white-space:nowrap}',
      '.dvs-network-card-panel{background-color:#e8e8e8e8;width:100%;box-sizing:border-box;margin:6px 0 8px;padding:4px;font-size:12px;border-radius:10px}.dvs-network-card-panel table{width:100%;table-layout:fixed;margin:0}.dvs-network-card-panel th,.dvs-network-card-panel td{overflow-wrap:anywhere;word-break:normal}',
      '@media(max-width:1100px){#dvs-network-layout{grid-template-columns:minmax(0,1fr)}#dvs-gateway-activity{grid-column:1;grid-row:1;width:100%}.dvs-network-cards-right{grid-column:1;grid-row:2;left:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;gap:0 8px;padding:0}}'
    ].join('');
    document.head.appendChild(style);
  }

  function leftCards(info) {
    var host = document.getElementById('dvs-network-sidebar-cards');
    if (!host) {
      host = document.createElement('div');
      host.id = 'dvs-network-sidebar-cards';
      host.className = 'dvs-network-cards dvs-network-cards-left';
      host.setAttribute('aria-label', 'Network status cards');
      info.parentNode.insertBefore(host, info.nextSibling);
    }
    return host;
  }

  function placeCards() {
    if (moving) return;
    var info = document.getElementById('modeInfo');
    var layout = document.getElementById('dvs-network-layout');
    var right = document.querySelector('#dvs-network-layout .dvs-network-cards-right');
    if (!info || !layout || !right) return;
    var left = leftCards(info);
    var cards = Array.from(info.querySelectorAll('table')).map(function (table) {
      var heading = table.querySelector('th');
      var name = heading ? heading.textContent.replace(/\s+/g, ' ').trim() : '';
      return {table: table, name: name, key: identity(name)};
    }).filter(function (card) { return cardNames.has(card.name) || /^DMR\s+.+\s+Master$/i.test(card.name); });
    if (!cards.length) return;
    moving = true;
    if (observer) observer.disconnect();
    cards.sort(function (a, b) { return a.name.localeCompare(b.name, 'en', {sensitivity: 'base'}); });
    cards.forEach(function (card, index) {
      var target = index < 3 && card.name !== 'M17 Net' ? left : right;
      var panel = Array.from(document.querySelectorAll('.dvs-network-card-panel')).find(function (item) {
        return item.dataset.cardIdentity === card.key;
      });
      if (!panel) {
        panel = document.createElement('fieldset');
        panel.className = 'dvs-network-card-panel';
        panel.dataset.cardIdentity = card.key;
      }
      var oldTable = panel.querySelector('table');
      if (oldTable !== card.table) {
        var before = card.table.previousElementSibling;
        if (before && before.tagName === 'BR') before.remove();
        card.table.style.width = '100%';
        card.table.style.tableLayout = 'fixed';
        if (oldTable) oldTable.replaceWith(card.table);
        else panel.appendChild(card.table);
      }
      if (panel.parentElement !== target) target.appendChild(panel);
    });
    if (observer) observer.observe(info, {childList: true, subtree: true});
    moving = false;
  }

  function start() {
    makeLayout();
    placeCards();
    var info = document.getElementById('modeInfo');
    if (info && !info.dataset.dvsDisplayLayoutObserved) {
      observer = new MutationObserver(placeCards);
      observer.observe(info, {childList: true, subtree: true});
      info.dataset.dvsDisplayLayoutObserved = '1';
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
  window.addEventListener('resize', placeCards);
})();
