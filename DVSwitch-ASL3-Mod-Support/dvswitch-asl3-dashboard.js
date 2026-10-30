/* Version: 1.1.2 — retain the ASL node target and refresh ASL favorites cleanly. */
(function () {
  'use strict';

  function normalizeHeader(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  var activeMode = '';
  var connectedNodes = [];
  var activityStarted = Object.create(null);
  var controlEndpoint = '/dvswitch/dvswitch-asl3-control.php';
  var digitalModePending = '';

  function routeRxMonitorOverHttps() {
    var player = window.DVSwitchPlayer;
    if (!player || !player.prototype || player.prototype.asl3AudioProxyInstalled) return;
    var play = player.prototype.play;
    player.prototype.play = function () {
      if (window.location.protocol === 'https:') this.socketURL = 'wss://' + window.location.host + '/dvswitch-audio/';
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
        var nodeText = connectedNodes.length ? connectedNodes.join(', ') : '-';
        if (value.textContent !== nodeText) value.textContent = nodeText;
      }
    });
  }

  // status.php reloads this table every second, so keep its target row tied to the live mode.
  function updateAnalogBridgeTarget(mode) {
    var info = document.getElementById('modeInfo');
    mode = String(mode || '').toUpperCase();
    if (!info || !mode) return;
    activeMode = mode;
    var label = mode === 'ASL' ? 'Node' : 'Tx TG/Ref';
    info.querySelectorAll('tr').forEach(function (row) {
      var heading = row.querySelector('th');
      var value = row.querySelector('td');
      var current = heading ? normalizeHeader(heading.textContent) : '';
      if (heading && value && (current === 'Tx TG/Ref' || current === 'Node')) {
        if (current !== label) heading.textContent = label;
        if (mode === 'ASL') {
          var nodeText = connectedNodes.length ? connectedNodes.join(', ') : '-';
          if (value.textContent !== nodeText) value.textContent = nodeText;
        }
      }
    });
    updateAnalogBridgeNode();
  }

  function watchAnalogBridgeInfo() {
    var info = document.getElementById('modeInfo');
    if (!info) return;
    // Reapply only the target label/value after DVSwitch replaces the status table.
    new MutationObserver(function () {
      var mode = modeFromAnalogBridge();
      if (mode) updateAnalogBridgeTarget(mode);
    }).observe(info, { childList: true, subtree: true });
  }

  function setTargetLabel(mode) {
    activeMode = String(mode || '').toUpperCase();
    updateAnalogBridgeTarget(activeMode);
    var input = document.getElementById('dvs-target-input');
    if (input) {
      // Keep the shared field hint compact enough to fit its existing width.
      input.placeholder = activeMode === 'ASL' ? 'Enter Node #' : 'Enter TG/Reflector';
      input.setAttribute('aria-label', activeMode === 'ASL' ? 'AllStar node number' : 'Talkgroup or reflector');
      input.style.width = activeMode === 'ASL' ? '14ch' : '18ch';
    }
    document.querySelectorAll('#dvs-mode-buttons [data-mode], #dvs-asl-mode-buttons [data-mode]').forEach(function (button) {
      if (button.dataset.mode === 'ASL') button.classList.toggle('selected', activeMode === 'ASL');
      else if (activeMode === 'ASL') button.classList.remove('selected');
    });
    var favorites = document.getElementById('dvs-favorites');
    if (favorites && activeMode === 'ASL') favorites.hidden = false;
    var links = document.getElementById('dvs-asl-links');
    if (links) links.hidden = activeMode !== 'ASL';
    var activity = document.getElementById('dvs-asl-activity');
    if (activity) activity.hidden = activeMode !== 'ASL';
    updateAnalogBridgeNode();
    if (activeMode === 'ASL') loadAslFavorites();
  }

  function modeFromAnalogBridge() {
    var info = document.getElementById('modeInfo');
    if (!info) return '';
    var mode = '';
    info.querySelectorAll('tr').forEach(function (row) {
      var heading = row.querySelector('th');
      var value = row.querySelector('td');
      if (heading && value && normalizeHeader(heading.textContent) === 'Mode') mode = normalizeHeader(value.textContent).toUpperCase();
    });
    return mode;
  }

  function ensureModeBar() {
    var bar = document.getElementById('dvs-mode-buttons');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'dvs-asl-mode-buttons';
      bar.setAttribute('aria-label', 'Select Mode');
      bar.style.cssText = 'text-align:center;margin:4px auto 5px';
      var title = document.createElement('div');
      title.textContent = 'Select Mode';
      title.style.cssText = 'font-weight:bold;margin-bottom:2px';
      bar.appendChild(title);
      var anchor = document.getElementById('modeInfo') || document.getElementById('lastHerd');
      if (anchor) anchor.insertAdjacentElement('beforebegin', bar);
      else document.body.insertBefore(bar, document.body.firstChild);
    }
    return bar;
  }

  function addAslButton() {
    var bar = ensureModeBar();
    if (bar.querySelector('[data-mode="ASL"]')) return;
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'button link';
    button.dataset.mode = 'ASL';
    button.textContent = 'ASL';
    button.setAttribute('aria-label', 'Select ASL mode');
    button.style.cssText = 'min-width:72px;height:32px;padding:4px 10px';
    button.addEventListener('click', async function () {
      button.disabled = true;
      var status = document.getElementById('dvs-target-message');
      if (status) status.textContent = '';
      try {
        var response = await fetch(controlEndpoint, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'mode' })
        });
        var result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || 'ASL mode switch failed.');
        setTargetLabel('ASL');
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
    bar.appendChild(button);
  }

  function ensureSharedTuneRow() {
    var root = document.getElementById('dvs-favorites');
    if (root) return root;
    // ASL Support also works without Mode Buttons: create one compact ASL-owned target row.
    root = document.createElement('section');
    root.id = 'dvs-favorites';
    root.style.cssText = 'text-align:center;margin:0 auto 8px';
    root.innerHTML = '<div class="dvs-favorites-control-line" style="display:inline-flex;align-items:center;justify-content:center;gap:8px;white-space:nowrap"><span class="dvs-favorites-heading">Favorites</span><select id="dvs-favorites-select" class="dvs-favorites-select" aria-label="ASL favorite"><option value="">Select favorite</option></select><button type="button" class="button link dvs-favorites-add-current">+ Favorite</button><form id="dvs-target-tuner" aria-label="Tune AllStar node" style="display:inline-flex;align-items:center;gap:6px"><input id="dvs-target-input" type="text" inputmode="numeric" maxlength="8" autocomplete="off" placeholder="Enter Node #" aria-label="AllStar node number" style="box-sizing:border-box;width:14ch;height:32px;padding:4px 8px"><button id="dvs-target-submit" type="submit" class="button link">Tune</button><span id="dvs-target-message" role="status" aria-live="polite"></span></form></div>';
    var bar = document.getElementById('dvs-asl-mode-buttons');
    bar.insertAdjacentElement('afterend', root);
    return root;
  }

  function addLinkControls() {
    if (document.getElementById('dvs-asl-links')) return;
    var bar = document.getElementById('dvs-mode-buttons') || document.getElementById('dvs-asl-mode-buttons');
    if (!bar) return;
    var root = document.createElement('fieldset');
    root.id = 'dvs-asl-links';
    root.hidden = true;
    root.style.cssText = 'box-sizing:border-box;width:min(95%,600px);margin:2px auto 4px;padding:0 8px 3px;border:1px solid #aaa;text-align:center';
    var legend = document.createElement('legend');
    legend.textContent = 'ASL Node Link';
    legend.style.cssText = 'padding:0 5px;font-size:12px;line-height:1';
    root.appendChild(legend);
    var actionContainer = document.createElement('div');
    actionContainer.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 14px';
    [['CONNECT', 'Connect'], ['DISCONNECT', 'Disconnect'], ['MONITOR', 'Monitor'], ['LOCAL_MONITOR', 'Local Monitor'], ['DISCONNECT_ALL', 'Disconnect All']].forEach(function (entry) {
      var label = document.createElement('label');
      label.style.cssText = 'display:inline-flex;align-items:center;margin:0;white-space:nowrap;font-size:12px';
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox'; checkbox.name = 'aslAction'; checkbox.value = entry[0];
      checkbox.addEventListener('change', function () {
        actionContainer.querySelectorAll('input[name="aslAction"]').forEach(function (other) { if (other !== checkbox) other.checked = false; });
        var input = document.getElementById('dvs-target-input');
        if (input) input.disabled = entry[0] === 'DISCONNECT_ALL' && checkbox.checked;
      });
      label.append(checkbox, document.createTextNode(' ' + entry[1]));
      actionContainer.appendChild(label);
    });
    root.appendChild(actionContainer);
    var replaceLabel = document.createElement('label');
    replaceLabel.style.cssText = 'display:inline-flex;align-items:center;margin:1px 0 0;white-space:nowrap;font-size:12px';
    var replaceCheckbox = document.createElement('input');
    replaceCheckbox.type = 'checkbox'; replaceCheckbox.id = 'dvs-asl-disconnect-before-connect'; replaceCheckbox.checked = true;
    replaceCheckbox.title = 'Disconnect existing external ASL links before connecting; the private bridge is preserved.';
    replaceLabel.append(replaceCheckbox, document.createTextNode(' Disconnect before Connect'));
    root.appendChild(replaceLabel);
    bar.insertAdjacentElement('afterend', root);
  }

  function endpointJson(url, options) {
    return fetch(url, options || { cache: 'no-store' }).then(function (response) {
      return response.json().then(function (result) {
        if (!response.ok || !result.ok) throw new Error(result.error || 'ASL request failed.');
        return result;
      });
    });
  }

  function loadAslFavorites() {
    var select = document.getElementById('dvs-favorites-select');
    if (!select || activeMode !== 'ASL') return;
    // Remove the previous mode's options while the ASL favorites request is in flight.
    select.replaceChildren(new Option('Select favorite', ''));
    endpointJson(controlEndpoint + '?favorites=1').then(function (result) {
      if (activeMode !== 'ASL') return;
      select.replaceChildren(new Option('Select favorite', ''));
      (result.favorites || []).forEach(function (favorite) {
        if (!favorite || !favorite.node || !favorite.name) return;
        var option = document.createElement('option');
        option.value = favorite.node;
        option.textContent = favorite.name + ' (' + favorite.node + ')';
        select.appendChild(option);
      });
    }).catch(function () {});
  }

  function addAslActivity() {
    var activity = document.getElementById('dvs-asl-activity');
    if (activity || !document.getElementById('lastHerd')) return;
    activity = document.createElement('section');
    activity.id = 'dvs-asl-activity'; activity.hidden = true;
    activity.style.cssText = 'margin:8px auto;max-width:1400px';
    var title = document.createElement('span'); title.textContent = 'ASL Gateway Activity'; title.style.cssText = 'font-weight:bold;font-size:14px';
    var card = document.createElement('fieldset');
    card.style.cssText = 'box-shadow:0 0 10px #999;background-color:#e8e8e8e8;width:min(95%,1400px);margin:10px auto 0;font-size:12px;border-radius:10px';
    var table = document.createElement('table'); table.style.cssText = 'width:100%;margin-top:3px;border-collapse:collapse';
    var header = document.createElement('tr');
    ['Time', 'Mode', 'Node', 'Name', 'Target', 'Src', 'Dur(s)', 'Loss', 'BER'].forEach(function (text) { var th = document.createElement('th'); th.textContent = text; header.appendChild(th); });
    var body = document.createElement('tbody'); body.id = 'dvs-asl-activity-rows';
    table.append(header, body); card.appendChild(table); activity.append(title, card);
    document.getElementById('lastHerd').insertAdjacentElement('beforebegin', activity);
    refreshActivity();
  }

  function refreshActivity() {
    var body = document.getElementById('dvs-asl-activity-rows');
    if (!body) return;
    fetch('/dvswitch/dvswitch-asl3-activity.php', { cache: 'no-store' }).then(function (response) { return response.json(); }).then(function (result) {
      if (!result || !result.ok || !Array.isArray(result.rows)) return;
      var header = document.querySelector('#dvs-asl-activity table tr');
      if (header && result.timezone) header.cells[0].textContent = 'Time (' + result.timezone + ')';
      connectedNodes = result.rows.map(function (row) { return String(row.node || '').trim(); }).filter(function (node) { return /^[0-9]{1,8}$/.test(node); });
      updateAnalogBridgeNode(); body.replaceChildren();
      if (!result.rows.length) {
        var tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 9; td.textContent = 'No external ASL nodes connected'; td.style.padding = '4px'; tr.appendChild(td); body.appendChild(tr); return;
      }
      result.rows.forEach(function (row) {
        var tr = document.createElement('tr'), duration = '—';
        if (row.keyed) {
          if (row.duration !== null && row.duration !== '' && Number.isFinite(Number(row.duration))) duration = String(Math.max(0, Number(row.duration)));
          else { if (!activityStarted[row.node]) activityStarted[row.node] = Date.now(); duration = String(Math.max(0, Math.floor((Date.now() - activityStarted[row.node]) / 1000))); }
        } else delete activityStarted[row.node];
        [row.time, row.mode, row.node, row.name || row.node, row.target || '—', row.source, duration, row.loss || '—', row.ber || '—'].forEach(function (value, index) {
          var td = document.createElement('td'); td.style.padding = '4px';
          if (index === 3) { var name = document.createElement('span'); name.setAttribute('style', 'display:block;color:#b5651d;font-weight:bold;white-space:normal;'); name.textContent = value; td.appendChild(name); }
          else td.textContent = value;
          tr.appendChild(td);
        });
        body.appendChild(tr);
      });
    }).catch(function () {});
  }

  function repairGatewaySourceHeading() {
    var table = document.querySelector('#lastHerd fieldset table');
    if (!table) return;
    var cells = table.querySelector('tr') ? table.querySelector('tr').querySelectorAll('th') : [];
    if (cells.length === 9 && normalizeHeader(cells[4].textContent) === 'Target' && normalizeHeader(cells[5].textContent) === '' && normalizeHeader(cells[6].textContent) === 'Dur(s)') cells[5].textContent = 'Src';
  }

  function watchGatewayActivity() {
    var activity = document.getElementById('lastHerd');
    if (!activity) return;
    repairGatewaySourceHeading();
    new MutationObserver(repairGatewaySourceHeading).observe(activity, { childList: true, subtree: true });
  }

  function showStatus(message) {
    var status = document.getElementById('dvs-target-message');
    if (status) status.textContent = message;
  }

  function selectedAslAction() {
    return document.querySelector('#dvs-asl-links input[name="aslAction"]:checked');
  }

  function installSharedActions() {
    var form = document.getElementById('dvs-target-tuner');
    var input = document.getElementById('dvs-target-input');
    var select = document.getElementById('dvs-favorites-select');
    var addFavorite = document.querySelector('.dvs-favorites-add-current');
    if (form) form.addEventListener('submit', function (event) {
      if (activeMode !== 'ASL') return;
      event.preventDefault(); event.stopImmediatePropagation();
      var actionBox = selectedAslAction();
      if (!actionBox) { showStatus('Select an ASL link action.'); return; }
      var action = actionBox.value;
      var node = input ? input.value.trim() : '';
      if (action !== 'DISCONNECT_ALL' && !/^[0-9]{1,8}$/.test(node)) { showStatus('Enter a valid node number.'); return; }
      var tune = document.getElementById('dvs-target-submit');
      if (tune) tune.disabled = true;
      if (input) input.disabled = true;
      var disconnect = document.getElementById('dvs-asl-disconnect-before-connect');
      endpointJson(controlEndpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'link', linkAction: action, node: action === 'DISCONNECT_ALL' ? '' : node, disconnectBeforeConnect: Boolean(action === 'CONNECT' && disconnect && disconnect.checked) }) })
        .then(function () {
          var messages = { CONNECT: 'Connected to Node ', DISCONNECT: 'Disconnected Node ', MONITOR: 'Monitoring Node ', LOCAL_MONITOR: 'Local Monitor Node ', DISCONNECT_ALL: 'Disconnected all nodes' };
          showStatus(messages[action] + (action === 'DISCONNECT_ALL' ? '' : node));
          actionBox.checked = false;
          if (input) input.disabled = false;
          refreshActivity();
        }).catch(function (error) { showStatus(error.message); })
        .finally(function () {
          if (tune) tune.disabled = false;
          var selected = selectedAslAction();
          if (input) input.disabled = Boolean(selected && selected.value === 'DISCONNECT_ALL');
        });
    }, true);
    if (select) select.addEventListener('change', function (event) {
      if (activeMode !== 'ASL' || !select.value) return;
      event.stopImmediatePropagation(); if (input) input.value = select.value;
      if (form && form.requestSubmit) form.requestSubmit();
      select.value = '';
    }, true);
    if (addFavorite) addFavorite.addEventListener('click', function (event) {
      if (activeMode !== 'ASL') return;
      event.preventDefault(); event.stopImmediatePropagation(); openAslFavorites(input ? input.value.trim() : '');
    }, true);
    var edit = document.querySelector('.dvs-favorites-edit');
    if (edit) edit.addEventListener('click', function (event) {
      if (activeMode !== 'ASL') return;
      event.preventDefault(); event.stopImmediatePropagation(); openAslFavorites('');
    }, true);
    var addRow = document.querySelector('.dvs-favorites-add');
    if (addRow) addRow.addEventListener('click', function (event) {
      var selector = document.querySelector('.dvs-favorites-mode');
      if (activeMode !== 'ASL' && (!selector || selector.value !== 'ASL')) return;
      event.preventDefault(); event.stopImmediatePropagation(); appendFavoriteRow({ name: '', node: '' });
    }, true);
    var save = document.querySelector('.dvs-favorites-save');
    if (save) save.addEventListener('click', function (event) {
      var selector = document.querySelector('.dvs-favorites-mode');
      if (activeMode !== 'ASL' && (!selector || selector.value !== 'ASL')) return;
      event.preventDefault(); event.stopImmediatePropagation(); saveAslFavorites();
    }, true);
    var selector = document.querySelector('.dvs-favorites-mode');
    if (selector) {
      var option = Array.from(selector.options).find(function (item) { return item.value === 'ASL'; });
      if (!option) { option = new Option('ASL', 'ASL'); selector.add(option); }
      selector.addEventListener('change', function (event) {
        if (selector.value !== 'ASL') return;
        event.stopImmediatePropagation(); fillAslFavorites();
      }, true);
    }
    var editor = document.querySelector('.dvs-favorites-editor');
    if (editor) editor.addEventListener('close', function () { if (activeMode === 'ASL') loadAslFavorites(); });
  }

  function editorElements() {
    var dialog = document.querySelector('.dvs-favorites-editor');
    return { dialog: dialog, rows: dialog && dialog.querySelector('.dvs-favorites-rows'), status: dialog && dialog.querySelector('.dvs-favorites-status'), selector: dialog && dialog.querySelector('.dvs-favorites-mode') };
  }

  function appendFavoriteRow(favorite) {
    var elements = editorElements();
    if (!elements.rows) return;
    var row = document.createElement('div'); row.className = 'dvs-favorite-edit-row';
    var name = document.createElement('input'); name.type = 'text'; name.maxLength = 64; name.value = favorite.name || ''; name.placeholder = 'Friendly name'; name.setAttribute('aria-label', 'Favorite name');
    var node = document.createElement('input'); node.type = 'text'; node.inputMode = 'numeric'; node.maxLength = 8; node.value = favorite.node || ''; node.placeholder = 'Node #'; node.setAttribute('aria-label', 'AllStar node number');
    var remove = document.createElement('button'); remove.type = 'button'; remove.className = 'button link'; remove.textContent = 'Delete'; remove.addEventListener('click', function () { row.remove(); });
    row.append(name, node, remove); elements.rows.appendChild(row);
  }

  function fillAslFavorites() {
    var elements = editorElements();
    if (!elements.rows) return;
    elements.rows.replaceChildren(); if (elements.status) elements.status.textContent = '';
    endpointJson(controlEndpoint + '?favorites=1').then(function (result) { (result.favorites || []).forEach(appendFavoriteRow); }).catch(function (error) { if (elements.status) elements.status.textContent = error.message; });
  }

  function openAslFavorites(addNode) {
    var elements = editorElements();
    if (!elements.dialog || !elements.rows) {
      if (addNode && /^[0-9]{1,8}$/.test(addNode) && !/^0+$/.test(addNode)) {
        Promise.all([endpointJson(controlEndpoint + '?favorites=1'), endpointJson(controlEndpoint + '?nodeNames=1')]).then(function (results) {
          var knownName = results[1].names && results[1].names[addNode] ? results[1].names[addNode] : '';
          var name = window.prompt('Friendly name for node ' + addNode + ':', knownName);
          if (!name) return;
          var favorites = (results[0].favorites || []).filter(function (favorite) { return String(favorite.node) !== addNode; });
          favorites.push({ name: name.trim(), node: addNode });
          return endpointJson(controlEndpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'saveFavorites', favorites: favorites }) }).then(loadAslFavorites);
        }).catch(function (error) { showStatus(error.message); });
      } else if (addNode) showStatus('Enter a valid node number before adding a favorite.');
      return;
    }
    if (elements.selector) elements.selector.value = 'ASL';
    elements.dialog.showModal();
    fillAslFavorites();
    if (!addNode) return;
    if (!/^[0-9]{1,8}$/.test(addNode) || /^0+$/.test(addNode)) { showStatus('Enter a valid node number before adding a favorite.'); return; }
    endpointJson(controlEndpoint + '?nodeNames=1').then(function (result) {
      var name = result.names && result.names[addNode] ? result.names[addNode] : '';
      appendFavoriteRow({ name: name, node: addNode });
      var elements = editorElements();
      if (elements.rows && elements.rows.lastElementChild) elements.rows.lastElementChild.firstElementChild.focus();
      if (elements.status) elements.status.textContent = name ? 'Review the friendly name, then select Save.' : 'Enter a friendly name, then select Save.';
    }).catch(function () { appendFavoriteRow({ name: '', node: addNode }); });
  }

  function saveAslFavorites() {
    var elements = editorElements(); if (!elements.rows) return;
    var favorites = Array.from(elements.rows.querySelectorAll('.dvs-favorite-edit-row')).map(function (row) { return { name: row.children[0].value.trim(), node: row.children[1].value.trim() }; });
    if (favorites.some(function (favorite) { return !favorite.name || !/^[0-9]{1,8}$/.test(favorite.node) || /^0+$/.test(favorite.node); })) { if (elements.status) elements.status.textContent = 'Enter a friendly name and valid node number for each favorite.'; return; }
    favorites.sort(function (a, b) { return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }) || a.node.localeCompare(b.node); });
    endpointJson(controlEndpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'saveFavorites', favorites: favorites }) }).then(function () { if (elements.status) elements.status.textContent = 'ASL favorites saved.'; loadAslFavorites(); }).catch(function (error) { if (elements.status) elements.status.textContent = error.message; });
  }

  document.addEventListener('DOMContentLoaded', function () {
    routeRxMonitorOverHttps();
    addAslButton();
    ensureSharedTuneRow();
    addLinkControls();
    addAslActivity();
    watchGatewayActivity();
    installSharedActions();
    var initialMode = modeFromAnalogBridge();
    if (initialMode) setTargetLabel(initialMode);
    watchAnalogBridgeInfo();
    var themeStyle = document.createElement('style');
    themeStyle.textContent = 'body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(odd) td{background-color:#111827!important;color:#e5e7eb!important;border-color:#374151!important}body.theme-dark #dvs-asl-activity fieldset table tr:nth-child(even) td,body.theme-auto.dvs-prefers-dark #dvs-asl-activity fieldset table tr:nth-child(even) td{background-color:#1f2937!important;color:#e5e7eb!important;border-color:#374151!important}#dvs-asl-mode-buttons button.selected{background-color:#008000}';
    document.head.appendChild(themeStyle);
  });
  document.addEventListener('click', function (event) {
    var button = event.target && event.target.closest ? event.target.closest('#dvs-mode-buttons [data-mode]') : null;
    if (!button || button.dataset.mode === 'ASL') return;
    digitalModePending = button.dataset.mode;
    window.setTimeout(function () { digitalModePending = ''; }, 10000);
  }, true);
  // Ignore the digital helper's startup status poll; only a clicked digital button can leave ASL.
  document.addEventListener('dvswitch-mode-buttons-mode', function (event) {
    var mode = String(event.detail && event.detail.mode || '').toUpperCase();
    if (digitalModePending && digitalModePending === mode) {
      digitalModePending = '';
      setTargetLabel(mode);
      return;
    }
    // The optional button script may emit stale startup status; keep ASL's shared controls intact.
    if (activeMode === 'ASL') setTargetLabel('ASL');
  });
  window.setInterval(refreshActivity, 5000);
})();
