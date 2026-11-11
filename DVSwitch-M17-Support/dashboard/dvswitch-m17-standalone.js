/* SPDX-License-Identifier: MIT
 * Version: 1.0.0 — Created 2026-11-11T11:30:00-05:00 by KE2HNI.
 * Supplies M17 dashboard controls when the optional shared Mode Buttons component is absent.
 */
(function () {
  'use strict';
  if (document.getElementById('dvs-mode-buttons') || document.getElementById('dvs-m17-standalone')) return;
  var rx = Array.from(document.querySelectorAll('button')).find(function (button) {
    return button.textContent.replace(/\s+/g, ' ').trim().includes('RX Monitor');
  });
  var host = rx && rx.parentElement;
  if (!host || !host.parentNode) return;

  var section = document.createElement('section');
  section.id = 'dvs-m17-standalone';
  section.setAttribute('aria-label', 'M17 mode and reflector controls');
  section.innerHTML = '<div class="dvs-m17-title">Select Mode</div><button type="button" class="button link dvs-m17-mode">M17</button><div class="dvs-m17-controls"><strong>Favorites</strong><select class="dvs-m17-list" aria-label="M17 reflector favorites"><option value="">Select favorite</option></select><button type="button" class="button link dvs-m17-edit">Edit</button><form class="dvs-m17-tune"><input type="text" maxlength="35" placeholder="M17-001-A" aria-label="M17 reflector and module"><button type="submit" class="button link">Tune</button><button type="button" class="button link dvs-m17-add">+ Favorite</button></form><span class="dvs-m17-message" role="status" aria-live="polite"></span></div><dialog class="dvs-m17-dialog"><h3>Edit M17 Favorites</h3><div class="dvs-m17-rows"></div><button type="button" class="button link dvs-m17-new">Add Favorite</button> <button type="button" class="button link dvs-m17-save">Save</button> <button type="button" class="button link dvs-m17-close">Cancel / Close</button><p class="dvs-m17-edit-message" role="status"></p></dialog>';
  var style = document.createElement('style');
  style.textContent = '#dvs-m17-standalone{text-align:center;margin:4px auto 8px}#dvs-m17-standalone .dvs-m17-title{font-weight:bold;margin-bottom:3px}#dvs-m17-standalone button{min-width:72px;height:32px;padding:4px 10px}#dvs-m17-standalone .dvs-m17-mode.selected{background:#008000}#dvs-m17-standalone .dvs-m17-controls{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:6px}#dvs-m17-standalone select,#dvs-m17-standalone input{box-sizing:border-box;height:32px;padding:4px 8px}#dvs-m17-standalone select{width:min(260px,25vw)}#dvs-m17-standalone input{width:10ch}#dvs-m17-standalone form{display:inline-flex;gap:6px;margin:0}#dvs-m17-standalone .dvs-m17-message{font-size:12px}#dvs-m17-standalone dialog{max-width:min(700px,94vw);max-height:80vh;overflow:auto;background:#111827;color:inherit;border:1px solid #8795a8;border-radius:8px}#dvs-m17-standalone .dvs-m17-row{display:flex;gap:6px;margin:5px;justify-content:center}#dvs-m17-standalone .dvs-m17-row input:first-child{width:min(35ch,45vw)}@media(max-width:600px){#dvs-m17-standalone .dvs-m17-controls{gap:4px}#dvs-m17-standalone select{width:36vw}}';
  document.head.appendChild(style);
  host.parentNode.insertBefore(section, host);

  var mode = section.querySelector('.dvs-m17-mode');
  var list = section.querySelector('.dvs-m17-list');
  var form = section.querySelector('.dvs-m17-tune');
  var input = form.querySelector('input');
  var message = section.querySelector('.dvs-m17-message');
  var dialog = section.querySelector('dialog');
  var rows = section.querySelector('.dvs-m17-rows');
  var editing = [];
  function api(payload, method) {
    return fetch('/dvswitch/dvswitch-m17-dashboard.php' + (method === 'GET' ? '?favorites=1' : ''), {
      method: method || 'POST', cache: 'no-store', headers: method === 'GET' ? {} : {'Content-Type': 'application/json'},
      body: method === 'GET' ? undefined : JSON.stringify(payload)
    }).then(function (response) { return response.json().then(function (data) { if (!response.ok || !data.ok) throw new Error(data.error || data.message || 'M17 request failed.'); return data; }); });
  }
  function load() {
    return api(null, 'GET').then(function (data) {
      list.replaceChildren(new Option('Select favorite', ''));
      data.favorites.forEach(function (favorite) {
        if (!favorite || typeof favorite.name !== 'string' || typeof favorite.target !== 'string') return;
        list.appendChild(new Option(favorite.name + ' (' + favorite.target + ')', favorite.target));
      });
    }).catch(function (error) { message.textContent = error.message; });
  }
  fetch('/dvswitch/dvswitch-m17-dashboard.php?status=1', {cache: 'no-store'})
    .then(function (response) { return response.json(); })
    .then(function (data) { if (data.ok && data.mode === 'M17') mode.classList.add('selected'); });
  function activate() {
    message.textContent = 'Switching to M17…';
    return api({action: 'activate'}).then(function (data) { mode.classList.add('selected'); message.textContent = data.message || 'M17 active.'; })
      .catch(function (error) { message.textContent = error.message; });
  }
  function tune(target) {
    if (!/^[A-Za-z0-9_-]{1,35}$/.test(target)) { message.textContent = 'Enter a valid reflector-module target.'; return Promise.resolve(); }
    message.textContent = 'Switching to M17 and tuning…';
    return api({action: 'activate'}).then(function () { return api({action: 'select', target: target}); })
      .then(function (data) { mode.classList.add('selected'); message.textContent = data.message || 'M17 reflector selected.'; })
      .catch(function (error) { message.textContent = error.message; });
  }
  mode.addEventListener('click', activate);
  list.addEventListener('change', function () { if (list.value) tune(list.value); list.value = ''; });
  form.addEventListener('submit', function (event) { event.preventDefault(); tune(input.value.trim()); });
  section.querySelector('.dvs-m17-add').addEventListener('click', function () {
    var target = input.value.trim();
    if (!target) { message.textContent = 'Enter a reflector-module target first.'; return; }
    api(null, 'GET').then(function (data) {
      var favorites = data.favorites;
      if (favorites.some(function (favorite) { return favorite.target.toUpperCase() === target.toUpperCase(); })) throw new Error('That target is already a favorite.');
      favorites.push({name: target, target: target});
      return api({action: 'save', favorites: favorites});
    }).then(load).then(function () { message.textContent = 'M17 favorite added.'; }).catch(function (error) { message.textContent = error.message; });
  });
  function renderEditor() {
    rows.replaceChildren();
    editing.forEach(function (favorite, index) {
      var row = document.createElement('div'); row.className = 'dvs-m17-row';
      var name = document.createElement('input'); name.maxLength = 35; name.value = favorite.name; name.placeholder = 'Favorite name';
      var target = document.createElement('input'); target.maxLength = 35; target.value = favorite.target; target.placeholder = 'M17-001-A';
      var remove = document.createElement('button'); remove.type = 'button'; remove.className = 'button link'; remove.textContent = 'Delete';
      name.addEventListener('input', function () { editing[index].name = name.value; });
      target.addEventListener('input', function () { editing[index].target = target.value; });
      remove.addEventListener('click', function () { editing.splice(index, 1); renderEditor(); });
      row.append(name, target, remove); rows.appendChild(row);
    });
  }
  section.querySelector('.dvs-m17-edit').addEventListener('click', function () {
    api(null, 'GET').then(function (data) { editing = data.favorites.map(function (favorite) { return {name: favorite.name, target: favorite.target}; }); renderEditor(); dialog.showModal(); })
      .catch(function (error) { message.textContent = error.message; });
  });
  section.querySelector('.dvs-m17-new').addEventListener('click', function () { editing.push({name: '', target: ''}); renderEditor(); });
  section.querySelector('.dvs-m17-close').addEventListener('click', function () { dialog.close(); });
  section.querySelector('.dvs-m17-save').addEventListener('click', function () {
    api({action: 'save', favorites: editing}).then(function () { dialog.close(); message.textContent = 'M17 favorites saved.'; return load(); })
      .catch(function (error) { section.querySelector('.dvs-m17-edit-message').textContent = error.message; });
  });
  load();
})();
