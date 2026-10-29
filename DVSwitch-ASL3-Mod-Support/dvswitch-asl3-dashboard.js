/* ASL link controls and Analog_Bridge target label. */
// Version: 1.0.2
(function () {
  'use strict';

  function normalizeHeader(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  var activeMode = '';
  var connectedNodes = [];
  var activityStarted = Object.create(null);
  // Names and favorites are ASL-owned so dashboard controls do not depend on Mode Buttons.
  var nodeNames = {};
  var favorites = [];

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
    // Keep the ASL mode control usable when the optional Mode Buttons repository is absent.
    var buttons = document.getElementById('dvs-mode-buttons');
    if (!buttons) {
      buttons = document.createElement('div');
      buttons.id = 'dvs-asl-mode-buttons';
      buttons.setAttribute('aria-label', 'Select Mode');
      buttons.style.cssText = 'margin:4px auto;text-align:center';
      var title = document.createElement('div'); title.textContent = 'Select Mode'; title.className = 'dvs-mode-buttons-title';
      buttons.appendChild(title);
      var rx = document.querySelector('#rxMonitor,button[onclick*="rxmon"],button[onclick*="RXMONITOR"]');
      var anchor = rx && rx.closest('div');
      (anchor || document.querySelector('.content center') || document.body).appendChild(buttons);
    }
    if (!buttons.querySelector('[data-mode="ASL"]')) {
      var modeButton = document.createElement('button');
      modeButton.type = 'button'; modeButton.className = 'button link'; modeButton.dataset.mode = 'ASL'; modeButton.textContent = 'ASL';
      buttons.appendChild(modeButton);
      modeButton.addEventListener('click', function () {
        sendControl({ action: 'mode' }).then(function () { setMode('ASL'); }).catch(showError);
      });
    }
    if (document.getElementById('dvs-asl-links')) return;
    var root = document.createElement('fieldset'); root.id = 'dvs-asl-links'; root.hidden = true;
    root.style.cssText = 'box-sizing:border-box;width:min(95%,600px);margin:2px auto 4px;padding:2px 8px 4px;border:1px solid #aaa;text-align:center';
    var legend = document.createElement('legend'); legend.textContent = 'ASL Node Link'; legend.style.cssText = 'padding:0 5px;font-size:12px;line-height:1'; root.appendChild(legend);
    var form = document.createElement('form'); form.id = 'dvs-asl-tuner'; form.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:3px';
    var input = document.createElement('input'); input.id = 'dvs-asl-node'; input.inputMode = 'numeric'; input.maxLength = 8; input.placeholder = 'Enter AllStar node number'; input.setAttribute('aria-label', 'AllStar node number');
    var favoriteSelect = document.createElement('select'); favoriteSelect.id = 'dvs-asl-favorites'; favoriteSelect.setAttribute('aria-label', 'ASL favorite'); favoriteSelect.innerHTML = '<option value="">Select favorite</option>';
    var tune = document.createElement('button'); tune.type = 'submit'; tune.className = 'button link'; tune.textContent = 'Tune';
    var save = document.createElement('button'); save.type = 'button'; save.className = 'button link'; save.textContent = '+ Favorite';
    var status = document.createElement('span'); status.id = 'dvs-asl-control-status'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    form.append(favoriteSelect, input, tune, save, status);
    favoriteSelect.addEventListener('change', function () { if (favoriteSelect.value) input.value = favoriteSelect.value; favoriteSelect.value = ''; });
    var actions = document.createElement('div'); actions.style.cssText = 'display:flex;flex-wrap:wrap;justify-content:center;gap:2px 14px;width:100%';
    [['CONNECT','Connect'],['DISCONNECT','Disconnect'],['MONITOR','Monitor'],['LOCAL_MONITOR','Local Monitor'],['DISCONNECT_ALL','Disconnect All']].forEach(function (entry) {
      var label = document.createElement('label'); label.style.cssText = 'display:inline-flex;align-items:center;margin:0;white-space:nowrap;font-size:12px';
      var checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = 'aslAction'; checkbox.value = entry[0];
      checkbox.addEventListener('change', function () { actions.querySelectorAll('input').forEach(function (other) { if (other !== checkbox) other.checked = false; }); input.disabled = entry[0] === 'DISCONNECT_ALL' && checkbox.checked; });
      label.append(checkbox, document.createTextNode(' ' + entry[1])); actions.appendChild(label);
    });
    form.appendChild(actions);
    var replaceLabel = document.createElement('label'); replaceLabel.style.cssText = 'display:inline-flex;align-items:center;margin:1px 0 0;white-space:nowrap;font-size:12px';
    var replace = document.createElement('input'); replace.type = 'checkbox'; replace.id = 'dvs-asl-disconnect-before-connect'; replace.checked = true;
    replace.title = 'Disconnect existing external ASL links before connecting; the private bridge is preserved.';
    replaceLabel.append(replace, document.createTextNode(' Disconnect before Connect')); form.appendChild(replaceLabel); root.appendChild(form);
    buttons.insertAdjacentElement('afterend', root);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var selected = actions.querySelector('input:checked');
      if (!selected) { status.textContent = 'Select an ASL link action.'; return; }
      sendControl({ action:'link', linkAction:selected.value, node:input.value.trim(), disconnectBeforeConnect:replace.checked })
        .then(function () { status.textContent = linkSuccessMessage(selected.value, input.value.trim()); selected.checked = false; input.disabled = false; refreshActivity(); })
        .catch(showError);
    });
    save.addEventListener('click', function () {
      var node = input.value.trim();
      if (!/^[0-9]{1,8}$/.test(node) || /^0+$/.test(node)) { status.textContent = 'Enter a valid node number first.'; return; }
      var name = window.prompt('Favorite name', nodeNames[node] || node);
      if (name === null) return;
      var next = favorites.filter(function (favorite) { return favorite.node !== node; });
      next.push({ name:name.trim(), node:node });
      sendControl({ action:'saveFavorites', favorites:next }).then(function () { favorites = next; loadFavorites(); status.textContent = 'Favorite saved.'; }).catch(showError);
    });
    loadFavorites(); loadNodeNames();
  }

  function sendControl(data) {
    return fetch('/dvswitch/dvswitch-asl3-control.php', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), cache:'no-store' })
      .then(function (response) { return response.json().then(function (result) { if (!response.ok || !result.ok) throw new Error(result.error || 'ASL request failed.'); return result; }); });
  }

  function showError(error) { var status = document.getElementById('dvs-asl-control-status'); if (status) status.textContent = error.message; }
  // Keep successful actions concise; detailed helper output remains available when an action fails.
  function linkSuccessMessage(action, node) {
    var messages = {
      CONNECT: 'Connected to Node ',
      DISCONNECT: 'Disconnected from Node ',
      MONITOR: 'Monitoring Node ',
      LOCAL_MONITOR: 'Local monitor on Node '
    };
    return action === 'DISCONNECT_ALL' ? 'Disconnected all nodes' : (messages[action] || 'ASL link updated') + node;
  }

  // Mode Buttons nests RX Monitor in its Favorites row, which is hidden in ASL mode.
  // Keep the existing audio button visible in ASL and restore its normal position for digital modes.
  function placeRxMonitor(mode) {
    var rxButton = Array.from(document.querySelectorAll('button')).find(function (button) {
      return button.textContent.replace(/\s+/g, ' ').trim().includes('RX Monitor');
    });
    if (!rxButton) return;
    var favoritesRow = document.querySelector('#dvs-favorites .dvs-favorites-control-line');
    var aslLinks = document.getElementById('dvs-asl-links');
    if (mode === 'ASL' && favoritesRow && favoritesRow.contains(rxButton) && aslLinks) {
      aslLinks.insertAdjacentElement('beforebegin', rxButton);
    } else if (mode !== 'ASL' && favoritesRow && !favoritesRow.contains(rxButton)) {
      favoritesRow.insertBefore(rxButton, favoritesRow.firstChild);
    }
  }

  function loadFavorites() {
    fetch('/dvswitch/dvswitch-asl3-control.php?favorites=1', {cache:'no-store'}).then(function (response) { return response.json(); }).then(function (result) {
      if (!result.ok || !Array.isArray(result.favorites)) return;
      favorites = result.favorites;
      var select = document.getElementById('dvs-asl-favorites'); if (!select) return;
      select.replaceChildren(new Option('Select favorite', ''));
      favorites.forEach(function (favorite) { var option = new Option(favorite.name + ' (' + favorite.node + ')', favorite.node); select.appendChild(option); });
    }).catch(function () {});
  }
  function loadNodeNames() {
    fetch('/dvswitch/dvswitch-asl3-control.php?nodeNames=1', {cache:'no-store'}).then(function (response) { return response.json(); }).then(function (result) { if (result.ok && result.names) nodeNames = result.names; }).catch(function () {});
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
    mode = String(mode || '').toUpperCase();
    setTargetLabel(mode);
    if (mode === 'ASL') {
      // ASL shares the mode-button row, so clear only digital selections before marking ASL.
      document.querySelectorAll('#dvs-mode-buttons [data-mode]').forEach(function (button) {
        if (button.dataset.mode !== 'ASL') button.classList.remove('selected');
      });
    }
    // Only ASL Support owns the ASL highlight; leave standard mode highlights to Mode Buttons.
    var aslButton = document.querySelector('#dvs-mode-buttons [data-mode="ASL"], #dvs-asl-mode-buttons [data-mode="ASL"]');
    if (aslButton) aslButton.classList.toggle('selected', mode === 'ASL');
    var links = document.getElementById('dvs-asl-links');
    if (links) links.hidden = mode !== 'ASL';
    var activity = document.getElementById('dvs-asl-activity');
    if (activity) activity.hidden = mode !== 'ASL';
    placeRxMonitor(mode);
  }

  function refresh() {
    var info = document.getElementById('modeInfo');
    if (!info) return;
    info.querySelectorAll('tr').forEach(function (row) {
      var heading = row.querySelector('th'), value = row.querySelector('td');
      if (heading && value && normalizeHeader(heading.textContent) === 'Mode') setMode(normalizeHeader(value.textContent).toUpperCase());
    });
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
    themeStyle.textContent = '#dvs-asl-mode-buttons button{min-width:72px;height:32px;padding:4px 10px}#dvs-asl-mode-buttons button.selected,#dvs-mode-buttons [data-mode="ASL"].selected{background-color:#008000}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td{background-color:#111827!important;color:#e5e7eb!important;border-color:#374151!important}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(even) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(even) td{background-color:#1f2937!important;color:#e5e7eb!important;border-color:#374151!important}';
    document.head.appendChild(themeStyle);
  });
  document.addEventListener('click', function (event) {
    var button = event.target.closest('#dvs-mode-buttons [data-mode]');
    if (button && button.dataset.mode !== 'ASL') setMode(button.dataset.mode);
  });
  document.addEventListener('dvswitch-mode-buttons-mode', function (event) {
    placeRxMonitor(event.detail && event.detail.mode);
  });
  window.setInterval(refresh, 5000);
  window.setInterval(refreshActivity, 5000);
})();
