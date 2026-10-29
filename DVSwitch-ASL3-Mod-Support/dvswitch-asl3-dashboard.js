/* ASL link controls and Analog_Bridge target label. */
// Version: 1.0.9
(function () {
  'use strict';

  function normalizeHeader(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  var activeMode = '';
  var pendingMode = '';
  var confirmedMode = '';
  var staleModeDuringTransition = '';
  var connectedNodes = [];
  var activityStarted = Object.create(null);
  // Names and favorites are ASL-owned so dashboard controls do not depend on Mode Buttons.
  var nodeNames = {};
  var favorites = [];
  var aslTuner = null;
  var aslNodeInput = null;
  var aslFavoriteSelect = null;
  var aslSaveFavorite = null;
  var aslEditFavorites = null;
  var aslControlStatus = null;

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
        beginModeTransition('ASL');
        sendControl({ action: 'mode' }).then(function () {
          acceptModeUpdate('ASL');
        }).catch(function (error) {
          cancelModeTransition();
          showError(error);
        });
      });
    }
    if (document.getElementById('dvs-asl-links')) return;
    var root = document.createElement('fieldset'); root.id = 'dvs-asl-links'; root.hidden = true;
    root.style.cssText = 'box-sizing:border-box;width:fit-content;max-width:95%;margin:2px auto 4px;padding:2px 8px 4px;border:1px solid #aaa;text-align:center';
    var legend = document.createElement('legend'); legend.textContent = 'ASL Node Link'; legend.style.cssText = 'padding:0 5px;font-size:12px;line-height:1'; root.appendChild(legend);
    var actions = document.createElement('div'); actions.style.cssText = 'display:flex;flex-wrap:wrap;justify-content:center;gap:2px 14px;width:100%';
    // Reuse Mode Buttons' existing one-line tuner; ASL adds a fallback only when Mode Buttons is absent.
    var standardTuner = document.getElementById('dvs-target-tuner');
    var standaloneLine = null;
    if (standardTuner) {
      aslTuner = standardTuner;
      aslNodeInput = document.getElementById('dvs-target-input');
      aslFavoriteSelect = document.getElementById('dvs-favorites-select');
      aslSaveFavorite = standardTuner.querySelector('.dvs-favorites-add-current');
      aslEditFavorites = document.querySelector('#dvs-favorites .dvs-favorites-edit');
      aslControlStatus = document.getElementById('dvs-target-message');
    } else {
      standaloneLine = document.createElement('div'); standaloneLine.id = 'dvs-asl-fallback-line';
      standaloneLine.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:4px;margin:2px auto 8px';
      aslTuner = document.createElement('form'); aslTuner.id = 'dvs-asl-tuner';
      aslTuner.style.cssText = 'display:inline-flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:4px';
      aslFavoriteSelect = document.createElement('select'); aslFavoriteSelect.id = 'dvs-asl-favorites';
      aslFavoriteSelect.setAttribute('aria-label', 'ASL favorite');
      aslFavoriteSelect.innerHTML = '<option value="">Select favorite</option>';
      aslNodeInput = document.createElement('input'); aslNodeInput.id = 'dvs-asl-node';
      aslNodeInput.inputMode = 'numeric'; aslNodeInput.maxLength = 8;
      aslNodeInput.placeholder = 'Enter Node #'; aslNodeInput.setAttribute('aria-label', 'AllStar node number');
      var fallbackTune = document.createElement('button'); fallbackTune.type = 'submit';
      fallbackTune.className = 'button link'; fallbackTune.textContent = 'Tune';
      aslSaveFavorite = document.createElement('button'); aslSaveFavorite.type = 'button';
      aslSaveFavorite.className = 'button link'; aslSaveFavorite.textContent = '+ Favorite';
      aslControlStatus = document.createElement('span'); aslControlStatus.id = 'dvs-asl-control-status';
      aslControlStatus.setAttribute('role', 'status'); aslControlStatus.setAttribute('aria-live', 'polite');
      aslTuner.append(aslFavoriteSelect, aslNodeInput, fallbackTune, aslSaveFavorite, aslControlStatus);
      standaloneLine.appendChild(aslTuner);
    }
    [['CONNECT','Connect'],['DISCONNECT','Disconnect'],['MONITOR','Monitor'],['LOCAL_MONITOR','Local Monitor'],['DISCONNECT_ALL','Disconnect All']].forEach(function (entry) {
      var label = document.createElement('label'); label.style.cssText = 'display:inline-flex;align-items:center;margin:0;white-space:nowrap;font-size:12px';
      var checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = 'aslAction'; checkbox.value = entry[0];
      checkbox.addEventListener('change', function () {
        actions.querySelectorAll('input').forEach(function (other) { if (other !== checkbox) other.checked = false; });
        aslNodeInput.disabled = entry[0] === 'DISCONNECT_ALL' && checkbox.checked;
      });
      label.append(checkbox, document.createTextNode(' ' + entry[1])); actions.appendChild(label);
    });
    var replaceLabel = document.createElement('label'); replaceLabel.style.cssText = 'display:inline-flex;align-items:center;margin:1px 0 0;white-space:nowrap;font-size:12px';
    var replace = document.createElement('input'); replace.type = 'checkbox'; replace.id = 'dvs-asl-disconnect-before-connect'; replace.checked = true;
    replace.title = 'Disconnect existing external ASL links before connecting; the private bridge is preserved.';
    replaceLabel.append(replace, document.createTextNode(' Disconnect before Connect'));
    root.append(actions, replaceLabel);
    buttons.insertAdjacentElement('afterend', root);
    if (standaloneLine) root.insertAdjacentElement('afterend', standaloneLine);
    if (aslFavoriteSelect) aslFavoriteSelect.addEventListener('change', function () {
      if (!aslFavoriteSelect.value) return;
      aslNodeInput.value = aslFavoriteSelect.value;
      aslTuner.requestSubmit();
      aslFavoriteSelect.value = '';
    });
    document.addEventListener('submit', function (event) {
      if (activeMode !== 'ASL' || event.target !== aslTuner) return;
      event.preventDefault(); event.stopImmediatePropagation();
      var selected = actions.querySelector('input:checked');
      var node = aslNodeInput.value.trim();
      if (!selected) { setControlMessage('Select an ASL link action.'); return; }
      if (selected.value !== 'DISCONNECT_ALL' && (!/^[0-9]{1,8}$/.test(node) || /^0+$/.test(node))) {
        setControlMessage('Enter a valid node number.'); return;
      }
      sendControl({ action:'link', linkAction:selected.value, node:node,
        disconnectBeforeConnect:replace.checked }).then(function () {
        setControlMessage(linkSuccessMessage(selected.value, node));
        selected.checked = false; aslNodeInput.disabled = false; refreshActivity();
      }).catch(showError);
    }, true);
    document.addEventListener('click', function (event) {
      if (activeMode !== 'ASL' || !aslSaveFavorite || !event.target.closest('#dvs-target-tuner .dvs-favorites-add-current, #dvs-asl-tuner button[type="button"]')) return;
      event.preventDefault(); event.stopImmediatePropagation();
      saveAslFavorite();
    }, true);
    loadNodeNames();
  }

  function sendControl(data) {
    return fetch('/dvswitch/dvswitch-asl3-control.php', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), cache:'no-store' })
      .then(function (response) { return response.json().then(function (result) { if (!response.ok || !result.ok) throw new Error(result.error || 'ASL request failed.'); return result; }); });
  }

  function setControlMessage(message) {
    if (!aslControlStatus) return;
    aslControlStatus.textContent = message;
    aslControlStatus.classList.toggle('error', /^Enter |^Select /.test(message));
  }

  function showError(error) { setControlMessage(error.message); }

  function saveAslFavorite() {
    var node = aslNodeInput.value.trim();
    if (!/^[0-9]{1,8}$/.test(node) || /^0+$/.test(node)) { setControlMessage('Enter a valid node number first.'); return; }
    var name = window.prompt('Favorite name', nodeNames[node] || node);
    if (name === null) return;
    var next = favorites.filter(function (favorite) { return favorite.node !== node; });
    next.push({ name:name.trim() || node, node:node });
    sendControl({ action:'saveFavorites', favorites:next }).then(function () {
      favorites = next; loadFavorites(); setControlMessage('Favorite saved.');
    }).catch(showError);
  }
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

  // Keep RX Monitor at the left edge of the single shared tuner/favorites line.
  function placeRxMonitor(mode) {
    var rxButton = Array.from(document.querySelectorAll('button')).find(function (button) {
      return button.textContent.replace(/\s+/g, ' ').trim().includes('RX Monitor');
    });
    if (!rxButton) return;
    var favoritesRow = document.querySelector('#dvs-favorites .dvs-favorites-control-line');
    var tunerRow = aslTuner && aslTuner.closest('.dvs-favorites-control-line, #dvs-asl-fallback-line');
    if (mode === 'ASL' && tunerRow) {
      tunerRow.insertBefore(rxButton, tunerRow.firstChild);
    } else if (mode !== 'ASL' && favoritesRow) {
      rxButton.classList.add('dvs-rx-monitor-inline');
      if (favoritesRow.contains(rxButton)) return;
      favoritesRow.insertBefore(rxButton, favoritesRow.firstChild);
    }
  }

  // Preserve the requested mode until Mode Buttons confirms its command result.
  function beginModeTransition(mode) {
    pendingMode = mode;
    staleModeDuringTransition = activeMode;
  }

  function acceptModeUpdate(mode) {
    mode = String(mode || '').toUpperCase();
    if (pendingMode && mode !== pendingMode) { setMode(activeMode); return; }
    if (confirmedMode && mode === staleModeDuringTransition) { setMode(confirmedMode); return; }
    if (confirmedMode && mode !== confirmedMode) {
      confirmedMode = '';
      staleModeDuringTransition = '';
    }
    if (pendingMode === mode) {
      confirmedMode = mode;
      pendingMode = '';
    }
    setMode(mode);
  }

  function clearModeTransition() {
    pendingMode = '';
    confirmedMode = '';
    staleModeDuringTransition = '';
  }

  function cancelModeTransition() {
    var previousMode = staleModeDuringTransition;
    clearModeTransition();
    if (previousMode) setMode(previousMode);
  }

  function loadFavorites() {
    fetch('/dvswitch/dvswitch-asl3-control.php?favorites=1', {cache:'no-store'}).then(function (response) { return response.json(); }).then(function (result) {
      if (!result.ok || !Array.isArray(result.favorites) || activeMode !== 'ASL' || !aslFavoriteSelect) return;
      favorites = result.favorites;
      aslFavoriteSelect.replaceChildren(new Option('Select favorite', ''));
      favorites.forEach(function (favorite) { var option = new Option(favorite.name + ' (' + favorite.node + ')', favorite.node); aslFavoriteSelect.appendChild(option); });
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
    activeMode = mode;
    setTargetLabel(mode);
    if (aslNodeInput) {
      aslNodeInput.placeholder = mode === 'ASL' ? 'Enter Node #' : 'Enter TG / Ref';
      aslNodeInput.setAttribute('aria-label', mode === 'ASL' ? 'AllStar node number' : 'Talkgroup or reflector ID');
    }
    if (aslEditFavorites) aslEditFavorites.hidden = mode === 'ASL';
    var favoritesRoot = document.getElementById('dvs-favorites');
    if (mode === 'ASL' && favoritesRoot) favoritesRoot.hidden = false;
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

  // Without Mode Buttons, keep ASL standalone by reading the dashboard's live mode row.
  function refreshStandaloneMode() {
    var info = document.getElementById('modeInfo');
    if (!info) return;
    info.querySelectorAll('tr').forEach(function (row) {
      var heading = row.querySelector('th'), value = row.querySelector('td');
      if (heading && value && normalizeHeader(heading.textContent) === 'Mode' && !pendingMode) {
        setMode(normalizeHeader(value.textContent));
      }
    });
  }

  function refresh() {
    // Mode Buttons sends the current mode after status checks and successful clicks.
    if (document.getElementById('dvs-mode-buttons')) return;
    refreshStandaloneMode();
  }

  document.addEventListener('DOMContentLoaded', function () {
    routeRxMonitorOverHttps();
    addLinkControls(); addAslActivity(); watchGatewayActivity(); refresh();
    var info = document.getElementById('modeInfo');
    if (info) new MutationObserver(function () {
      if (document.getElementById('dvs-mode-buttons')) {
        // status.php replaces the table during refresh; reapply the confirmed mode label.
        if (activeMode) setTargetLabel(activeMode);
        return;
      }
      var mode = activeMode;
      info.querySelectorAll('tr').forEach(function (row) {
        var heading = row.querySelector('th');
        var value = row.querySelector('td');
        if (heading && value && normalizeHeader(heading.textContent) === 'Mode') mode = normalizeHeader(value.textContent).toUpperCase();
      });
      setMode(mode);
    }).observe(info, { childList: true, subtree: true });
    var themeStyle = document.createElement('style');
    themeStyle.textContent = '#dvs-asl-mode-buttons button{min-width:72px;height:32px;padding:4px 10px}#dvs-asl-mode-buttons button.selected,#dvs-mode-buttons [data-mode="ASL"].selected{background-color:#008000}#dvs-asl-links{width:fit-content;max-width:95%}#dvs-target-input{box-sizing:border-box;width:min(18ch,55vw)}#dvs-target-tuner{display:inline-flex;vertical-align:middle;align-items:center;justify-content:center;gap:6px;margin:0;min-height:34px;white-space:nowrap}#dvs-target-submit,#dvs-favorites .dvs-favorites-add-current{min-width:64px;height:32px;padding:4px 10px}#dvs-asl-fallback-line #dvs-asl-node{box-sizing:border-box;width:min(18ch,55vw);height:32px;padding:4px 8px}#dvs-asl-fallback-line select{box-sizing:border-box;width:min(24ch,32vw);height:32px;padding:4px 8px}#dvs-asl-fallback-line button{min-width:64px;height:32px;padding:4px 10px}#dvs-favorites .dvs-favorites-edit[hidden]{display:none!important}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td{background-color:#111827!important;color:#e5e7eb!important;border-color:#374151!important}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(even) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(even) td{background-color:#1f2937!important;color:#e5e7eb!important;border-color:#374151!important}@media(max-width:600px){#dvs-target-input,#dvs-asl-fallback-line #dvs-asl-node{width:min(18ch,42vw)}}';
    document.head.appendChild(themeStyle);
  });
  document.addEventListener('click', function (event) {
    var button = event.target.closest('#dvs-mode-buttons [data-mode]');
    if (button && button.dataset.mode !== 'ASL') {
      // Track the requested destination, but let Mode Buttons confirm it before changing the UI.
      if (activeMode === 'ASL') beginModeTransition(button.dataset.mode);
    }
  });
  document.addEventListener('dvswitch-mode-buttons-mode', function (event) {
    acceptModeUpdate(event.detail && event.detail.mode);
  });
  window.setInterval(refresh, 5000);
  window.setInterval(refreshActivity, 5000);
})();
