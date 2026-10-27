/* ASL link controls and Analog_Bridge target label. */
(function () {
  'use strict';

  function normalizeHeader(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  var activeMode = '';
  var connectedNodes = [];
  var activityStarted = Object.create(null);

  function routeRxMonitorOverHttps() {
    var player = window.DVSwitchPlayer;
    if (!player || !player.prototype || player.prototype.asl3AudioProxyInstalled) return;
    var play = player.prototype.play;
    player.prototype.play = function () {
      if (window.location.protocol === 'https:') {
        this.socketURL = 'wss://' + window.location.host + '/dvswitch-audio/';
      }
      return play.apply(this, arguments);
    };
    player.prototype.asl3AudioProxyInstalled = true;
  }

  function updateAnalogBridgeNode() {
    if (activeMode !== 'ASL') return;
    var info = document.getElementById('modeInfo');
    if (!info) return;
    info.querySelectorAll('tr').forEach(function (row) {
      var heading = row.querySelector('th');
      var value = row.querySelector('td');
      if (heading && value && normalizeHeader(heading.textContent) === 'Node') {
        var nodeText = connectedNodes.length ? connectedNodes.join(', ') : '—';
        if (value.textContent !== nodeText) value.textContent = nodeText;
      }
    });
  }

  function setTargetLabel(mode) {
    activeMode = mode;
    var label = mode === 'ASL' ? 'Node' : 'Tx TG/Ref';
    var info = document.getElementById('modeInfo');
    if (!info) return;
    info.querySelectorAll('th').forEach(function (cell) {
      var heading = normalizeHeader(cell.textContent);
      if ((heading === 'Tx TG/Ref' || heading === 'Node') && heading !== label) {
        cell.textContent = label;
      }
    });
    updateAnalogBridgeNode();
  }

  function repairGatewaySourceHeading() {
    var table = document.querySelector('#lastHerd fieldset table');
    if (!table) return;
    var heading = table.querySelector('tr');
    var cells = heading ? heading.querySelectorAll('th') : [];
    if (cells.length === 9 && normalizeHeader(cells[4].textContent) === 'Target' &&
        normalizeHeader(cells[5].textContent) === '' && normalizeHeader(cells[6].textContent) === 'Dur(s)') {
      cells[5].textContent = 'Src';
    }
  }

  function watchGatewayActivity() {
    var activity = document.getElementById('lastHerd');
    if (!activity) return;
    repairGatewaySourceHeading();
    new MutationObserver(repairGatewaySourceHeading).observe(activity, { childList: true, subtree: true });
  }

  function addLinkControls() {
    var root = document.getElementById('dvs-asl-links');
    if (root || !document.getElementById('dvs-mode-buttons')) return;
    root = document.createElement('fieldset');
    root.id = 'dvs-asl-links';
    root.hidden = true;
    root.style.cssText = 'box-sizing:border-box;width:min(95%,600px);margin:2px auto 4px;padding:0 8px 3px;border:1px solid #aaa;text-align:center';
    var legend = document.createElement('legend');
    legend.textContent = 'ASL Node Link';
    legend.style.cssText = 'padding:0 5px;font-size:12px;line-height:1';
    root.appendChild(legend);
    var actionContainer = document.createElement('div');
    actionContainer.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 14px';
    var actionOptions = [
      ['CONNECT', 'Connect'], ['DISCONNECT', 'Disconnect'], ['MONITOR', 'Monitor'],
      ['LOCAL_MONITOR', 'Local Monitor'], ['DISCONNECT_ALL', 'Disconnect All']
    ];
    actionOptions.forEach(function (entry) {
      var label = document.createElement('label');
      label.style.cssText = 'display:inline-flex;align-items:center;margin:0;white-space:nowrap;font-size:12px';
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.name = 'aslAction';
      checkbox.value = entry[0];
      checkbox.addEventListener('change', function () {
        actionContainer.querySelectorAll('input[name="aslAction"]').forEach(function (other) { if (other !== checkbox) other.checked = false; });
        var target = document.getElementById('dvs-target-input');
        if (target) target.disabled = entry[0] === 'DISCONNECT_ALL' && checkbox.checked;
      });
      label.append(checkbox, document.createTextNode(' ' + entry[1]));
      actionContainer.appendChild(label);
    });
    root.appendChild(actionContainer);
    var replaceLabel = document.createElement('label');
    replaceLabel.style.cssText = 'display:inline-flex;align-items:center;margin:1px 0 0;white-space:nowrap;font-size:12px';
    var replaceCheckbox = document.createElement('input');
    replaceCheckbox.type = 'checkbox';
    replaceCheckbox.id = 'dvs-asl-disconnect-before-connect';
    // Default to replacing prior external links whenever Connect is selected.
    replaceCheckbox.checked = true;
    replaceCheckbox.title = 'Disconnect existing external ASL links before connecting; the private bridge is preserved.';
    replaceLabel.append(replaceCheckbox, document.createTextNode(' Disconnect before Connect'));
    root.appendChild(replaceLabel);
    var buttons = document.getElementById('dvs-mode-buttons');
    buttons.insertAdjacentElement('afterend', root);
  }

  function addAslActivity() {
    var activity = document.getElementById('dvs-asl-activity');
    if (activity || !document.getElementById('lastHerd')) return;
    activity = document.createElement('section');
    activity.id = 'dvs-asl-activity';
    activity.hidden = true;
    activity.style.cssText = 'margin:8px auto;max-width:1400px';
    var title = document.createElement('span');
    title.textContent = 'ASL Gateway Activity';
    title.style.cssText = 'font-weight:bold;font-size:14px';
    var card = document.createElement('fieldset');
    card.style.cssText = 'box-shadow:0 0 10px #999;background-color:#e8e8e8e8;width:min(95%,1400px);margin:10px auto 0;font-size:12px;border-radius:10px';
    var table = document.createElement('table');
    table.style.cssText = 'width:100%;margin-top:3px;border-collapse:collapse';
    var header = document.createElement('tr');
    // Mirror Gateway Activity columns; ASL keying and duration come from Allmon3-style AMI status.
    ['Time', 'Mode', 'Node', 'Name', 'Target', 'Src', 'Dur(s)', 'Loss', 'BER'].forEach(function (text) {
      var th = document.createElement('th'); th.textContent = text; header.appendChild(th);
    });
    var body = document.createElement('tbody');
    body.id = 'dvs-asl-activity-rows';
    table.append(header, body);
    card.appendChild(table);
    activity.append(title, card);
    document.getElementById('lastHerd').insertAdjacentElement('beforebegin', activity);
    refreshActivity();
  }

  function refreshActivity() {
    var body = document.getElementById('dvs-asl-activity-rows');
    if (!body) return;
    fetch('/dvswitch/dvswitch-asl3-activity.php', { cache: 'no-store' })
      .then(function (response) { return response.json(); })
      .then(function (result) {
        if (!result || !result.ok || !Array.isArray(result.rows)) return;
        var header = document.querySelector('#dvs-asl-activity table tr');
        if (header && result.timezone) header.cells[0].textContent = 'Time (' + result.timezone + ')';
        connectedNodes = result.rows.map(function (row) { return String(row.node || '').trim(); })
          .filter(function (node) { return /^[0-9]{1,8}$/.test(node); });
        updateAnalogBridgeNode();
        body.replaceChildren();
        if (!result.rows.length) {
          var emptyRow = document.createElement('tr');
          var emptyCell = document.createElement('td');
          emptyCell.colSpan = 9;
          emptyCell.textContent = 'No external ASL nodes connected';
          emptyCell.style.padding = '4px';
          emptyRow.appendChild(emptyCell);
          body.appendChild(emptyRow);
          return;
        }
        result.rows.forEach(function (row) {
          var tr = document.createElement('tr');
          var duration = '—';
          if (row.keyed) {
            if (row.duration !== null && row.duration !== '' && Number.isFinite(Number(row.duration))) {
              duration = String(Math.max(0, Number(row.duration)));
            } else {
              if (!activityStarted[row.node]) activityStarted[row.node] = Date.now();
              duration = String(Math.max(0, Math.floor((Date.now() - activityStarted[row.node]) / 1000)));
            }
          } else {
            delete activityStarted[row.node];
          }
          [row.time, row.mode, row.node, row.name || row.node, row.target || '—', row.source,
            duration, row.loss || '—', row.ber || '—'].forEach(function (value, index) {
            var td = document.createElement('td'); td.style.padding = '4px';
            if (index === 3) {
              var name = document.createElement('span');
              name.setAttribute('style', 'display:block;color:#b5651d;font-weight:bold;white-space:normal;');
              name.textContent = value;
              td.appendChild(name);
            } else {
              td.textContent = value;
            }
            tr.appendChild(td);
          });
          body.appendChild(tr);
        });
      }).catch(function () {});
  }

  function setMode(mode) {
    setTargetLabel(mode);
    var links = document.getElementById('dvs-asl-links');
    if (links) links.hidden = mode !== 'ASL';
    var activity = document.getElementById('dvs-asl-activity');
    if (activity) activity.hidden = mode !== 'ASL';
  }

  function refresh() {
    fetch('/dvswitch/dvswitch-mode-buttons.php?status=1', { cache: 'no-store' })
      .then(function (response) { return response.json(); })
      .then(function (result) { if (result && result.ok) setMode(result.mode); })
      .catch(function () {});
  }

  document.addEventListener('DOMContentLoaded', function () {
    routeRxMonitorOverHttps();
    addLinkControls(); addAslActivity(); watchGatewayActivity(); refresh();
    var info = document.getElementById('modeInfo');
    if (info) new MutationObserver(function () {
      var mode = activeMode;
      info.querySelectorAll('tr').forEach(function (row) {
        var heading = row.querySelector('th');
        var value = row.querySelector('td');
        if (heading && value && normalizeHeader(heading.textContent) === 'Mode') mode = normalizeHeader(value.textContent).toUpperCase();
      });
      setTargetLabel(mode);
    }).observe(info, { childList: true, subtree: true });
    var themeStyle = document.createElement('style');
    themeStyle.textContent = 'body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td{background-color:#111827!important;color:#e5e7eb!important;border-color:#374151!important}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(even) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(even) td{background-color:#1f2937!important;color:#e5e7eb!important;border-color:#374151!important}';
    document.head.appendChild(themeStyle);
  });
  document.addEventListener('dvswitch-mode-buttons-mode', function (event) {
    var mode = event.detail && event.detail.mode;
    setMode(mode);
  });
  window.setInterval(refresh, 5000);
  window.setInterval(refreshActivity, 5000);
})();
