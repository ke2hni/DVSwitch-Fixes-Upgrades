/* ASL3 network status cell and Analog_Bridge target label. */
(function () {
  'use strict';

  function normalizeHeader(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function setTargetLabel(mode) {
    var label = mode === 'ASL' ? 'Node' : 'Tx TG/Ref';
    var info = document.getElementById('modeInfo');
    if (!info) return;
    info.querySelectorAll('th').forEach(function (cell) {
      var heading = normalizeHeader(cell.textContent);
      if (heading === 'Tx TG/Ref' || heading === 'Node') {
        cell.textContent = label;
      }
    });
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

  function setAslNetworkState(mode) {
    var cell = document.getElementById('dvswitch-asl3-net-status');
    if (!cell) return;
    var active = mode === 'ASL';
    cell.style.backgroundColor = active ? '#12AD2A' : '#b00';
    cell.style.color = active ? '#030' : '#f9f9f9';
    cell.setAttribute('aria-label', active ? 'ASL mode selected' : 'ASL mode not selected');
  }

  function addLinkControls() {
    var root = document.getElementById('dvs-asl-links');
    if (root || !document.getElementById('dvs-mode-buttons')) return;
    root = document.createElement('fieldset');
    root.id = 'dvs-asl-links';
    root.hidden = true;
    root.style.cssText = 'margin:8px auto;padding:8px;max-width:760px;border:1px solid #aaa;text-align:center';
    var legend = document.createElement('legend');
    legend.textContent = 'ASL Node Link';
    root.appendChild(legend);
    var form = document.createElement('form');
    form.id = 'dvs-asl-link-form';
    var actions = [
      ['CONNECT', 'Connect'], ['DISCONNECT', 'Disconnect'], ['MONITOR', 'Monitor'],
      ['LOCAL_MONITOR', 'Local Monitor'], ['DISCONNECT_ALL', 'Disconnect All']
    ];
    actions.forEach(function (entry) {
      var label = document.createElement('label');
      label.style.cssText = 'display:inline-block;margin:4px 8px;white-space:nowrap';
      var checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.name = 'aslAction';
      checkbox.value = entry[0];
      checkbox.addEventListener('change', function () {
        form.querySelectorAll('input[name="aslAction"]').forEach(function (other) { if (other !== checkbox) other.checked = false; });
        var target = document.getElementById('dvs-target-input');
        if (target) target.disabled = entry[0] === 'DISCONNECT_ALL' && checkbox.checked;
      });
      label.append(checkbox, document.createTextNode(' ' + entry[1]));
      form.appendChild(label);
    });
    var submit = document.createElement('button');
    submit.type = 'submit';
    submit.className = 'button link';
    submit.textContent = 'Run ASL Link Action';
    form.appendChild(submit);
    var message = document.createElement('span');
    message.id = 'dvs-asl-link-message';
    message.setAttribute('role', 'status');
    message.style.cssText = 'display:block;min-height:1.4em;margin-top:6px';
    root.append(form, message);
    var buttons = document.getElementById('dvs-mode-buttons');
    buttons.insertAdjacentElement('afterend', root);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var selected = form.querySelector('input[name="aslAction"]:checked');
      var target = document.getElementById('dvs-target-input');
      if (!selected) { message.textContent = 'Select one ASL link action.'; return; }
      if (selected.value !== 'DISCONNECT_ALL' && (!target || !/^[0-9]{1,8}$/.test(target.value.trim()) || /^0+$/.test(target.value.trim()))) {
        message.textContent = 'Enter a non-zero numeric AllStar node number in the Tune field.';
        if (target) target.focus();
        return;
      }
      submit.disabled = true;
      message.textContent = 'Sending ASL link command…';
      fetch('/dvswitch/dvswitch-mode-buttons.php', {
        method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ aslAction: selected.value, target: selected.value === 'DISCONNECT_ALL' ? '' : target.value.trim() })
      }).then(function (response) { return response.json().then(function (result) { if (!response.ok || !result.ok) throw new Error(result.error || result.message || 'ASL action failed.'); return result; }); })
        .then(function (result) { message.textContent = result.message || 'ASL link action sent.'; selected.checked = false; })
        .catch(function (error) { message.textContent = error.message; })
        .finally(function () { submit.disabled = false; if (target) target.disabled = false; });
    });
  }

  function addAslActivity() {
    var activity = document.getElementById('dvs-asl-activity');
    if (activity || !document.getElementById('lastHerd')) return;
    activity = document.createElement('section');
    activity.id = 'dvs-asl-activity';
    activity.hidden = true;
    activity.style.cssText = 'margin:8px auto;max-width:1000px';
    var title = document.createElement('h3');
    title.textContent = 'ASL Gateway Activity';
    var table = document.createElement('table');
    table.style.cssText = 'width:100%;border-collapse:collapse';
    var header = document.createElement('tr');
    ['Time', 'Node', 'Name', 'Activity'].forEach(function (text) {
      var th = document.createElement('th'); th.textContent = text; header.appendChild(th);
    });
    var body = document.createElement('tbody');
    body.id = 'dvs-asl-activity-rows';
    table.append(header, body);
    activity.append(title, table);
    document.getElementById('lastHerd').insertAdjacentElement('afterend', activity);
    refreshActivity();
  }

  function refreshActivity() {
    var body = document.getElementById('dvs-asl-activity-rows');
    if (!body) return;
    fetch('/dvswitch/dvswitch-asl3-activity.php', { cache: 'no-store' })
      .then(function (response) { return response.json(); })
      .then(function (result) {
        if (!result || !result.ok || !Array.isArray(result.rows)) return;
        body.replaceChildren();
        result.rows.forEach(function (row) {
          var tr = document.createElement('tr');
          [row.time, row.node, row.name || row.node, row.activity].forEach(function (value) {
            var td = document.createElement('td'); td.textContent = value; td.style.padding = '4px'; tr.appendChild(td);
          });
          body.appendChild(tr);
        });
      }).catch(function () {});
  }

  function setMode(mode) {
    setTargetLabel(mode);
    setAslNetworkState(mode);
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

  document.addEventListener('DOMContentLoaded', function () { addLinkControls(); addAslActivity(); watchGatewayActivity(); refresh(); });
  document.addEventListener('dvswitch-mode-buttons-mode', function (event) {
    var mode = event.detail && event.detail.mode;
    setMode(mode);
  });
  window.setInterval(refresh, 5000);
  window.setInterval(refreshActivity, 5000);
})();
