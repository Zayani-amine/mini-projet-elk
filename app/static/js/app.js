(function () {
  'use strict';

  const asArray = value => (Array.isArray(value) ? value : []);

  const numberOr = (value, fallback) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  };

  const formatNumber = (value, digits) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    const fraction = digits === undefined ? 1 : digits;
    return new Intl.NumberFormat('fr-FR', {
      minimumFractionDigits: fraction,
      maximumFractionDigits: fraction
    }).format(number);
  };

  const formatInteger = value => formatNumber(value, 0);

  const formatDate = value => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('fr-FR', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(date);
  };

  const toIso = value => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toISOString();
  };

  const buildQuery = values => {
    const params = new URLSearchParams();
    Object.keys(values || {}).forEach(key => {
      const value = values[key];
      if (value !== null && value !== undefined && String(value).trim() !== '') {
        params.set(key, String(value));
      }
    });
    return params;
  };

  const errorMessage = (payload, fallback) => {
    const error = payload && payload.error ? payload.error : payload;
    if (!error) return fallback;
    if (error.message) return String(error.message);
    if (typeof error.detail === 'string' && error.detail) return error.detail;
    return fallback;
  };

  const fetchJson = async (url, options) => {
    const response = await fetch(url, Object.assign(
      { headers: { Accept: 'application/json' } },
      options || {}
    ));
    let payload = null;
    try {
      payload = await response.json();
    } catch (parseError) {
      payload = null;
    }
    if (!response.ok) {
      throw new Error(errorMessage(payload, 'Le service a répondu avec le statut ' + response.status + '.'));
    }
    if (payload === null) {
      throw new Error('Réponse JSON invalide.');
    }
    return payload;
  };

  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value === null || value === undefined ? '' : String(value);
  };

  const show = (id, visible) => {
    const element = document.getElementById(id);
    if (element) element.classList.toggle('d-none', !visible);
  };

  const makeChart = (id, config, hasData) => {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const wrapper = canvas.closest('.chart-wrap');
    const enabled = typeof Chart !== 'undefined';
    if (wrapper) wrapper.classList.toggle('chart-empty', !hasData || !enabled);
    if (enabled) new Chart(canvas, config);
  };

  if (typeof Chart !== 'undefined' && Chart.defaults && Chart.defaults.font) {
    Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
    Chart.defaults.color = '#6c757d';
  }

  async function initDashboard() {
    if (!document.getElementById('dashboard-loading')) return;
    show('dashboard-loading', true);
    show('dashboard-error', false);
    try {
      const data = await fetchJson('/api/v1/stats');
      const temperatures = asArray(data.temperature_avg);
      const alerts = asArray(data.critical_alerts_daily);
      const energy = asArray(data.energy_realtime);
      const occupancy = asArray(data.occupancy_rate);
      const maintenance = asArray(data.maintenance_forecast);
      const average = values => {
        const clean = values.filter(value => Number.isFinite(value));
        return clean.length ? clean.reduce((total, value) => total + value, 0) / clean.length : null;
      };
      const temperatureAverage = average(temperatures.map(row => numberOr(row && row.avg, NaN)));
      const occupancyAverage = average(occupancy.map(row => numberOr(row && row.rate, NaN)));
      const lastAlert = alerts.length ? alerts[alerts.length - 1] : null;
      const lastEnergy = energy.length ? energy[energy.length - 1] : null;

      setText('kpi-temperature', temperatureAverage === null ? '—' : formatNumber(temperatureAverage) + ' °C');
      setText('kpi-alerts', lastAlert ? formatInteger(numberOr(lastAlert.count, 0)) : '—');
      setText('kpi-energy', lastEnergy ? formatNumber(numberOr(lastEnergy.total, 0)) + ' kWh' : '—');
      setText('kpi-occupancy', occupancyAverage === null ? '—' : formatNumber(occupancyAverage) + ' %');
      setText('kpi-maintenance', formatInteger(maintenance.length));

      const badge = document.getElementById('cache-badge');
      if (badge) {
        badge.textContent = data.cache_hit ? 'Cache : données en cache' : 'Cache : données calculées';
        badge.className = 'badge ' + (data.cache_hit ? 'text-bg-success' : 'text-bg-secondary');
      }

      const axisOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      };

      makeChart('chart-temperature', {
        type: 'bar',
        data: {
          labels: temperatures.map(row => (row && row.zone) || '—'),
          datasets: [{
            label: 'Température (°C)',
            data: temperatures.map(row => numberOr(row && row.avg, 0)),
            backgroundColor: '#0d6efd',
            borderRadius: 6
          }]
        },
        options: Object.assign({}, axisOptions, {
          scales: { y: { beginAtZero: true, title: { display: true, text: '°C' } } }
        })
      }, temperatures.length > 0);

      makeChart('chart-alerts', {
        type: 'line',
        data: {
          labels: alerts.map(row => (row && row.day) || '—'),
          datasets: [{
            label: 'Alertes critiques',
            data: alerts.map(row => numberOr(row && row.count, 0)),
            borderColor: '#dc3545',
            backgroundColor: 'rgba(220, 53, 69, 0.15)',
            pointBackgroundColor: '#dc3545',
            fill: true,
            tension: 0.3
          }]
        },
        options: axisOptions
      }, alerts.length > 0);

      makeChart('chart-energy', {
        type: 'line',
        data: {
          labels: energy.map(row => (row && row.minute) || '—'),
          datasets: [{
            label: 'Énergie (kWh)',
            data: energy.map(row => numberOr(row && row.total, 0)),
            borderColor: '#198754',
            backgroundColor: 'rgba(25, 135, 84, 0.15)',
            pointBackgroundColor: '#198754',
            fill: true,
            tension: 0.3
          }]
        },
        options: axisOptions
      }, energy.length > 0);

      makeChart('chart-occupancy', {
        type: 'doughnut',
        data: {
          labels: occupancy.map(row => (row && row.room) || '—'),
          datasets: [{
            label: 'Taux d’occupation (%)',
            data: occupancy.map(row => numberOr(row && row.rate, 0)),
            backgroundColor: ['#0d6efd', '#198754', '#ffc107', '#fd7e14', '#6f42c1', '#20c997'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '65%',
          plugins: {
            legend: { position: 'right' },
            tooltip: { callbacks: { label: context => context.label + ' : ' + formatNumber(context.parsed) + ' %' } }
          }
        }
      }, occupancy.length > 0);

      makeChart('chart-maintenance', {
        type: 'bar',
        data: {
          labels: maintenance.map(row => (row && row.equipment_id) || '—'),
          datasets: [{
            label: 'Usure (%)',
            data: maintenance.map(row => numberOr(row && row.wear_level, 0)),
            backgroundColor: '#fd7e14',
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                afterLabel: context => {
                  const row = maintenance[context.dataIndex] || {};
                  return [
                    row.predicted_failure ? 'Panne : ' + row.predicted_failure : '',
                    row.estimated_due_date ? 'Échéance : ' + formatDate(row.estimated_due_date) : ''
                  ].filter(Boolean);
                }
              }
            }
          },
          scales: { x: { beginAtZero: true, max: 100 } }
        }
      }, maintenance.length > 0);

      const maintenanceBody = document.getElementById('maintenance-body');
      if (maintenanceBody) {
        maintenanceBody.replaceChildren();
        maintenance.forEach(row => {
          const item = row || {};
          const wear = numberOr(item.wear_level, NaN);
          const tr = document.createElement('tr');
          [
            item.equipment_id || '—',
            item.predicted_failure || '—',
            Number.isFinite(wear) ? formatNumber(wear, 0) + ' %' : '—',
            formatDate(item.estimated_due_date)
          ].forEach(value => {
            const td = document.createElement('td');
            td.textContent = String(value);
            tr.appendChild(td);
          });
          maintenanceBody.appendChild(tr);
        });
      }
      show('maintenance-table-card', maintenance.length > 0);
    } catch (error) {
      setText('dashboard-error-message', ' ' + error.message);
      show('dashboard-error', true);
      ['kpi-temperature', 'kpi-alerts', 'kpi-energy', 'kpi-occupancy', 'kpi-maintenance'].forEach(id => setText(id, '—'));
    } finally {
      show('dashboard-loading', false);
    }
  }

  function initUpload() {
    const input = document.getElementById('upload-file');
    const zone = document.getElementById('upload-dropzone');
    const pick = document.getElementById('upload-pick');
    const submit = document.getElementById('upload-submit');
    if (!input || !zone || !pick || !submit) return;

    let selected = null;
    const allowed = /\.(csv|json|txt)$/i;

    const setError = message => {
      setText('upload-error', message || '');
      show('upload-error', Boolean(message));
    };

    const setBusy = busy => {
      submit.disabled = busy || !selected;
      pick.disabled = busy;
    };

    const choose = file => {
      setError('');
      show('upload-result', false);
      if (!file || !allowed.test(file.name)) {
        selected = null;
        input.value = '';
        setText('upload-file-name', file ? 'Format non accepté : ' + file.name : 'Aucun fichier sélectionné');
        if (file) setError('Formats autorisés : .csv, .json et .txt.');
        setBusy(false);
        return;
      }
      selected = file;
      setText('upload-file-name', file.name);
      setBusy(false);
    };

    pick.addEventListener('click', () => input.click());
    input.addEventListener('change', () => choose(input.files && input.files[0]));

    ['dragenter', 'dragover'].forEach(type => {
      zone.addEventListener(type, event => {
        event.preventDefault();
        zone.classList.add('drag-over');
      });
    });
    ['dragleave', 'dragend'].forEach(type => {
      zone.addEventListener(type, () => zone.classList.remove('drag-over'));
    });
    zone.addEventListener('drop', event => {
      event.preventDefault();
      zone.classList.remove('drag-over');
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      choose(file);
    });

    submit.addEventListener('click', () => {
      if (!selected) return;
      setError('');
      show('upload-result', false);
      show('upload-progress-wrap', true);
      setText('upload-progress-text', '0 %');
      setBusy(true);
      const bar = document.getElementById('upload-progress-bar');
      if (bar) {
        bar.style.width = '0%';
        bar.classList.add('progress-bar-animated');
      }
      const updateProgress = percent => {
        const value = Math.max(0, Math.min(100, Math.round(percent)));
        setText('upload-progress-text', value + ' %');
        if (bar) bar.style.width = value + '%';
        const wrapper = document.querySelector('#upload-progress-wrap .progress');
        if (wrapper) wrapper.setAttribute('aria-valuenow', String(value));
      };
      const form = new FormData();
      form.append('file', selected, selected.name);
      const xhr = new XMLHttpRequest();
      const finish = () => {
        setBusy(false);
        show('upload-progress-wrap', false);
      };

      xhr.open('POST', '/api/v1/upload');
      xhr.upload.addEventListener('progress', event => {
        if (event.lengthComputable) updateProgress(event.loaded * 100 / event.total);
      });
      xhr.upload.addEventListener('load', () => updateProgress(100));
      xhr.addEventListener('load', () => {
        let payload = null;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch (parseError) {
          payload = null;
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          const result = payload || {};
          setText('upload-result-title', 'Fichier envoyé : ' + (result.original_name || selected.name));
          setText('upload-file-id', result.file_id || '—');
          setText('upload-result-meta', [
            result.log_type ? 'Type : ' + result.log_type : '',
            result.logs_count !== undefined ? formatInteger(result.logs_count) + ' lignes' : '',
            result.status ? 'Statut : ' + result.status : ''
          ].filter(Boolean).join(' · '));
          show('upload-result', true);
          selected = null;
          input.value = '';
          setText('upload-file-name', 'Aucun fichier sélectionné');
        } else {
          setError(errorMessage(payload, 'Échec de l’envoi (' + xhr.status + ').'));
        }
        finish();
      });
      xhr.addEventListener('error', () => {
        setError('Échec réseau lors de l’envoi.');
        finish();
      });
      xhr.send(form);
    });
  }

  async function initHistory() {
    const list = document.getElementById('history-list');
    if (!list) return;
    try {
      const data = await fetchJson('/api/v1/history?size=10');
      const rows = asArray(data.results);
      list.replaceChildren();
      if (!rows.length) {
        const item = document.createElement('li');
        item.className = 'list-group-item px-0 text-muted small';
        item.textContent = 'Aucune recherche enregistrée.';
        list.appendChild(item);
      }
      rows.forEach(entry => {
        const row = entry || {};
        const item = document.createElement('li');
        item.className = 'list-group-item px-0';
        const title = document.createElement('div');
        title.className = 'small fw-semibold';
        title.textContent = row.query ? '« ' + row.query + ' »' : 'Tous les logs';
        const meta = document.createElement('div');
        meta.className = 'small text-muted';
        meta.textContent = [
          formatDate(row.created_at),
          row.results_count !== undefined ? formatInteger(row.results_count) + ' résultat(s)' : '',
          row.cache_hit ? 'cache' : ''
        ].filter(Boolean).join(' · ');
        item.appendChild(title);
        item.appendChild(meta);
        list.appendChild(item);
      });
      setText('history-status', formatInteger(data.total) + ' recherche(s) enregistrée(s)');
    } catch (error) {
      setText('history-status', error.message);
    }
  }

  function initSearch() {
    const form = document.getElementById('search-form');
    if (!form) return;
    form.addEventListener('submit', event => {
      event.preventDefault();
      const values = new FormData(form);
      const params = buildQuery({
        q: values.get('q'),
        log_type: values.get('log_type'),
        from: toIso(values.get('from')),
        to: toIso(values.get('to')),
        severity: values.get('severity'),
        zone: values.get('zone'),
        entity_id: values.get('entity_id'),
        sort: values.get('sort')
      });
      window.location.href = '/results?' + params.toString();
    });
    initHistory();
  }

  async function initResults() {
    const body = document.getElementById('results-body');
    if (!body) return;

    const params = new URLSearchParams(window.location.search);
    const page = Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1);
    const sortSelect = document.getElementById('results-sort');
    if (sortSelect) sortSelect.value = params.get('sort') === 'oldest' ? 'oldest' : 'recent';
    setText('results-query', params.get('q') || 'Tous les logs');

    const apiParams = new URLSearchParams(params);
    apiParams.delete('size');
    apiParams.set('size', '50');
    apiParams.set('page', String(page));

    const buildResultsUrl = overrides => {
      const next = new URLSearchParams(params);
      next.delete('size');
      Object.keys(overrides || {}).forEach(key => {
        const value = overrides[key];
        if (value === null || value === undefined || value === '') next.delete(key);
        else next.set(key, String(value));
      });
      next.set('size', '50');
      next.set('page', String((overrides && overrides.page) || page));
      return '/results?' + next.toString();
    };

    if (sortSelect) {
      sortSelect.addEventListener('change', () => {
        window.location.href = buildResultsUrl({ sort: sortSelect.value, page: 1 });
      });
    }
    const exportButton = document.getElementById('export-csv');
    if (exportButton) {
      exportButton.addEventListener('click', () => {
        window.open('/api/v1/logs/export?' + apiParams.toString(), '_blank', 'noopener');
      });
    }

    show('results-loading', true);
    show('results-error', false);
    try {
      const data = await fetchJson('/api/v1/search?' + apiParams.toString());
      const rows = asArray(data.results);
      const current = Number(data.page) || page;
      const size = Number(data.size) || 50;

      setText('results-total', formatInteger(data.total));
      setText('results-took', data.took_ms !== undefined ? '· ' + formatInteger(data.took_ms) + ' ms' : '');
      setText('results-count', rows.length + ' résultat(s) affiché(s)');
      setText('page-label', 'Page ' + current);

      const appendCell = (tr, value) => {
        const td = document.createElement('td');
        td.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
        tr.appendChild(td);
        return td;
      };

      body.replaceChildren();
      if (!rows.length) {
        const tr = document.createElement('tr');
        const td = appendCell(tr, 'Aucun résultat pour ces critères.');
        td.colSpan = 7;
        td.className = 'text-center text-muted py-4';
        body.appendChild(tr);
      } else {
        rows.forEach((hit, index) => {
          const row = hit || {};
          const tr = document.createElement('tr');
          appendCell(tr, formatDate(row['@timestamp']));
          appendCell(tr, row.log_type);
          appendCell(tr, row.entity_id || row.sensor_id || row.meter_id || row.room_id);
          appendCell(tr, row.zone);
          appendCell(tr, row.message || row.rule || row.measure || row.equipment_type || row.predicted_failure || row.energy_type);
          appendCell(tr, row.severity);

          const actionCell = appendCell(tr, '');
          actionCell.className = 'text-end';
          const detailId = 'detail-' + index;
          const toggle = document.createElement('button');
          toggle.type = 'button';
          toggle.className = 'btn btn-sm btn-outline-primary';
          toggle.textContent = 'Détails';
          toggle.setAttribute('aria-controls', detailId);
          toggle.setAttribute('aria-expanded', 'false');
          actionCell.appendChild(toggle);
          body.appendChild(tr);

          const detailRow = document.createElement('tr');
          detailRow.id = detailId;
          detailRow.className = 'd-none';
          const detailCell = document.createElement('td');
          detailCell.colSpan = 7;
          const pre = document.createElement('pre');
          pre.className = 'json-block mb-0';
          pre.textContent = JSON.stringify(row, null, 2);
          detailCell.appendChild(pre);
          detailRow.appendChild(detailCell);
          body.appendChild(detailRow);

          toggle.addEventListener('click', () => {
            const hidden = detailRow.classList.toggle('d-none');
            toggle.setAttribute('aria-expanded', String(!hidden));
            toggle.textContent = hidden ? 'Détails' : 'Masquer';
          });
        });
      }

      const previous = document.getElementById('prev-page');
      if (previous) {
        previous.disabled = current <= 1;
        previous.onclick = () => {
          window.location.href = buildResultsUrl({ page: Math.max(1, current - 1) });
        };
      }
      const next = document.getElementById('next-page');
      if (next) {
        next.disabled = current * size >= Number(data.total || 0);
        next.onclick = () => {
          window.location.href = buildResultsUrl({ page: current + 1 });
        };
      }
    } catch (error) {
      setText('results-error-message', ' ' + error.message);
      show('results-error', true);
      body.replaceChildren();
    } finally {
      show('results-loading', false);
    }
  }

  const start = () => {
    initDashboard();
    initUpload();
    initSearch();
    initResults();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
