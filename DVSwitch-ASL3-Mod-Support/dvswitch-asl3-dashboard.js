/* ASL link controls and Analog_Bridge target label. */
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
    var tuner = document.getElementById('dvs-target-tuner');
    if (!tuner) {
      var fallback = document.createElement('div');
      fallback.id = 'dvs-asl-fallback-tuner';
      fallback.hidden = true;
      fallback.style.cssText = 'margin:4px auto;text-align:center';
      fallback.innerHTML = '<select id="dvs-asl-favorites" aria-label="ASL favorite"><option value="">Select favorite</option></select> <input id="dvs-target-input" inputmode="numeric" maxlength="8" placeholder="Enter Node #" aria-label="AllStar node number"> <button id="dvs-target-submit" type="button" class="button link">Tune</button> <button type="button" class="button link" id="dvs-asl-save-favorite">+ Favorite</button>';
      buttons.insertAdjacentElement('afterend', fallback);
    }
    var tunerInput = document.getElementById('dvs-target-input');
    var tunerButton = document.getElementById('dvs-target-submit');
    var standardFavorites = document.querySelector('#dvs-favorites .dvs-favorites-select');
    var standardEdit = document.querySelector('#dvs-favorites .dvs-favorites-edit');
    var favoriteSelect = document.getElementById('dvs-asl-favorites');
    if (!favoriteSelect) {
      favoriteSelect = document.createElement('select');
      favoriteSelect.id = 'dvs-asl-favorites';
      favoriteSelect.setAttribute('aria-label', 'ASL favorite');
      favoriteSelect.innerHTML = '<option value="">Select favorite</option>';
      if (tunerInput) tunerInput.parentNode.insertBefore(favoriteSelect, tunerInput);
    }
    if (standardFavorites) standardFavorites.hidden = true;
    if (standardEdit) standardEdit.hidden = true;

    var root = document.getElementById('dvs-asl-links');
    if (!root) {
      root = document.createElement('fieldset'); root.id = 'dvs-asl-links'; root.hidden = true;
      root.style.cssText = 'box-sizing:border-box;width:fit-content;max-width:95%;margin:2px auto 4px;padding:2px 8px 4px;border:1px solid #aaa;text-align:center';
      var legend = document.createElement('legend'); legend.textContent = 'ASL Node Link'; legend.style.cssText = 'padding:0 5px;font-size:12px;line-height:1'; root.appendChild(legend);
      var actions = document.createElement('div'); actions.id = 'dvs-asl-actions';
      actions.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 14px';
      [['CONNECT','Connect'],['DISCONNECT','Disconnect'],['MONITOR','Monitor'],['LOCAL_MONITOR','Local Monitor'],['DISCONNECT_ALL','Disconnect All']].forEach(function (entry) {
        var label = document.createElement('label'); label.style.cssText = 'display:inline-flex;align-items:center;margin:0;white-space:nowrap;font-size:12px';
        var checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = 'aslAction'; checkbox.value = entry[0];
        checkbox.addEventListener('change', function () { actions.querySelectorAll('input').forEach(function (other) { if (other !== checkbox) other.checked = false; }); if (tunerInput) tunerInput.disabled = entry[0] === 'DISCONNECT_ALL' && checkbox.checked; });
        label.append(checkbox, document.createTextNode(' ' + entry[1])); actions.appendChild(label);
      });
      root.appendChild(actions);
      var replaceLabel = document.createElement('label'); replaceLabel.style.cssText = 'display:inline-flex;align-items:center;margin:1px 0 0;white-space:nowrap;font-size:12px';
      var replace = document.createElement('input'); replace.type = 'checkbox'; replace.id = 'dvs-asl-disconnect-before-connect'; replace.checked = true;
      replace.title = 'Disconnect existing external ASL links before connecting; the private bridge is preserved.';
      replaceLabel.append(replace, document.createTextNode(' Disconnect before Connect')); root.appendChild(replaceLabel);
      var status = document.createElement('span'); status.id = 'dvs-asl-control-status'; status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
      status.style.cssText = 'display:block;min-height:1em;font-size:12px'; root.appendChild(status);
      buttons.insertAdjacentElement('afterend', root);
    }
    if (tuner && !tuner.dataset.aslSubmitHandler) {
      tuner.dataset.aslSubmitHandler = '1';
      tuner.addEventListener('submit', function (event) {
        if (activeMode !== 'ASL') return;
        event.preventDefault(); event.stopImmediatePropagation();
        var selected = root.querySelector('#dvs-asl-actions input:checked');
        var node = tunerInput ? tunerInput.value.trim() : '';
        var action = selected ? selected.value : 'CONNECT';
        if (action !== 'DISCONNECT_ALL' && (!/^[0-9]{1,8}$/.test(node) || /^0+$/.test(node))) { showError(new Error('Enter a valid node number.')); return; }
        sendControl({ action:'link', linkAction:action, node:node, disconnectBeforeConnect:document.getElementById('dvs-asl-disconnect-before-connect').checked })
          .then(function () { var status = document.getElementById('dvs-asl-control-status'); if (status) status.textContent = action === 'CONNECT' ? 'Connected to Node ' + node : action.replace(/_/g, ' ') + (node ? ' Node ' + node : '') + ' complete.'; if (selected) selected.checked = false; if (tunerInput) tunerInput.disabled = false; refreshActivity(); })
          .catch(showError);
      }, true);
    }
    if (tunerButton && !tunerButton.dataset.aslSubmitHandler) {
      tunerButton.dataset.aslSubmitHandler = '1';
      tunerButton.addEventListener('click', function (event) {
        if (activeMode !== 'ASL' || tuner) return;
        event.preventDefault();
        if (tunerInput && tunerInput.value.trim()) sendControl({ action:'link', linkAction:'CONNECT', node:tunerInput.value.trim(), disconnectBeforeConnect:true })
          .then(function () { var status = document.getElementById('dvs-asl-control-status'); if (status) status.textContent = 'Connected to Node ' + tunerInput.value.trim(); refreshActivity(); }).catch(showError);
      }, true);
    }
    favoriteSelect.addEventListener('change', function () { if (favoriteSelect.value && tunerInput) { tunerInput.value = favoriteSelect.value; if (activeMode === 'ASL' && tuner) tuner.requestSubmit(); } favoriteSelect.value = ''; });
    var addFavorite = document.querySelector('#dvs-target-tuner .dvs-favorites-add-current') || document.getElementById('dvs-asl-save-favorite');
    if (addFavorite && !addFavorite.dataset.aslSaveHandler) {
      addFavorite.dataset.aslSaveHandler = '1';
      addFavorite.addEventListener('click', function (event) {
        if (activeMode !== 'ASL') return;
        event.preventDefault(); event.stopImmediatePropagation();
        var node = tunerInput ? tunerInput.value.trim() : '';
        if (!/^[0-9]{1,8}$/.test(node) || /^0+$/.test(node)) { showError(new Error('Enter a valid node number first.')); return; }
        var name = window.prompt('Favorite name', nodeNames[node] || node);
        if (name === null) return;
        var next = favorites.filter(function (favorite) { return favorite.node !== node; });
        next.push({ name:name.trim() || node, node:node });
        sendControl({ action:'saveFavorites', favorites:next }).then(function () { favorites = next; loadFavorites(); var status = document.getElementById('dvs-asl-control-status'); if (status) status.textContent = 'Favorite saved.'; }).catch(showError);
      }, true);
    }
    loadFavorites(); loadNodeNames();
  }

  function sendControl(data) {
    return fetch('/dvswitch/dvswitch-asl3-control.php', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), cache:'no-store' })
      .then(function (response) { return response.json().then(function (result) { if (!response.ok || !result.ok) throw new Error(result.error || 'ASL request failed.'); return result; }); });
  }

  function showError(error) { var status = document.getElementById('dvs-asl-control-status'); if (status) status.textContent = error.message; }
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
    // Only ASL Support owns the ASL highlight; leave standard mode highlights to Mode Buttons.
    var aslButton = document.querySelector('#dvs-mode-buttons [data-mode="ASL"], #dvs-asl-mode-buttons [data-mode="ASL"]');
    if (aslButton) aslButton.classList.toggle('selected', mode === 'ASL');
    if (mode === 'ASL') {
      document.querySelectorAll('#dvs-mode-buttons [data-mode]').forEach(function (button) { button.classList.remove('selected'); });
    }
    var links = document.getElementById('dvs-asl-links');
    if (links) links.hidden = mode !== 'ASL';
    var favoritesRoot = document.getElementById('dvs-favorites');
    if (favoritesRoot) favoritesRoot.hidden = mode !== 'ASL' && !['BM', 'TGIF', 'STFU', 'YSF', 'P25', 'NXDN', 'DSTAR'].includes(mode);
    var standardFavorites = document.querySelector('#dvs-favorites .dvs-favorites-select');
    var standardEdit = document.querySelector('#dvs-favorites .dvs-favorites-edit');
    var aslFavorites = document.getElementById('dvs-asl-favorites');
    if (standardFavorites) standardFavorites.hidden = mode === 'ASL';
    if (standardEdit) standardEdit.hidden = mode === 'ASL';
    if (aslFavorites) aslFavorites.hidden = mode !== 'ASL';
    var target = document.getElementById('dvs-target-input');
    if (target) {
      target.placeholder = mode === 'ASL' ? 'Enter Node #' : 'Enter TG / Ref';
      target.setAttribute('aria-label', mode === 'ASL' ? 'AllStar node number' : 'Talkgroup or reflector ID');
      target.style.width = mode === 'ASL' ? '14ch' : '18ch';
      target.inputMode = mode === 'ASL' ? 'numeric' : 'text';
      target.maxLength = mode === 'ASL' ? 8 : 32;
    }
    var fallbackTuner = document.getElementById('dvs-asl-fallback-tuner');
    if (fallbackTuner) fallbackTuner.hidden = mode !== 'ASL';
    var activity = document.getElementById('dvs-asl-activity');
    if (activity) activity.hidden = mode !== 'ASL';
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
    themeStyle.textContent = '#dvs-asl-mode-buttons button{min-width:72px;height:32px;padding:4px 10px}#dvs-asl-mode-buttons button.selected{background-color:#008000}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td{background-color:#111827!important;color:#e5e7eb!important;border-color:#374151!important}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(even) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(even) td{background-color:#1f2937!important;color:#e5e7eb!important;border-color:#374151!important}';
    document.head.appendChild(themeStyle);
  });
  // Mode Buttons emits this only after its server-side mode command succeeds.
  // Waiting for confirmation prevents a stale ASL status refresh from undoing
  // the selected mode while the ASL link is being disconnected.
  document.addEventListener('dvswitch-mode-buttons-mode', function (event) {
    var mode = event.detail && event.detail.mode;
    if (mode) setMode(mode);
  });
  window.setInterval(refresh, 5000);
  window.setInterval(refreshActivity, 5000);
})();
