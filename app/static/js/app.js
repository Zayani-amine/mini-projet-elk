(function () {
  'use strict';

  const asArray = value => (Array.isArray(value) ? value : []);

  const numberOr = (value, fallback) => {
    if (value === null || value === undefined || value === '') return fallback;
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  };

  const formatNumber = (value, digits) => {
    if (value === null || value === undefined || value === '') return 'n/d';
    const number = Number(value);
    if (!Number.isFinite(number)) return 'n/d';
    const fraction = digits === undefined ? 1 : digits;
    return new Intl.NumberFormat('fr-FR', {
      minimumFractionDigits: fraction,
      maximumFractionDigits: fraction
    }).format(number);
  };

  const formatInteger = value => formatNumber(value, 0);

  const formatValue = (value, unit) => {
    if (value === null || value === undefined || value === '') return 'n/d';
    const number = Number(value);
    if (!Number.isFinite(number)) return 'n/d';
    return formatNumber(number) + (unit ? ' ' + unit : '');
  };

  const formatDate = (value, fallback) => {
    if (!value) return fallback || 'n/d';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return fallback || String(value);
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

  const toLocalInput = value => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  };

  const cleanLabel = value => {
    const text = String(value === null || value === undefined ? '' : value).trim();
    return text || 'Sans libellé';
  };

  const formatAge = seconds => {
    if (seconds === null || seconds === undefined || !Number.isFinite(Number(seconds))) return 'n/d';
    let remaining = Math.max(0, Math.floor(Number(seconds)));
    const days = Math.floor(remaining / 86400);
    remaining -= days * 86400;
    const hours = Math.floor(remaining / 3600);
    remaining -= hours * 3600;
    const minutes = Math.floor(remaining / 60);
    remaining -= minutes * 60;
    const parts = [];
    if (days) parts.push(days + ' j');
    if (hours) parts.push(hours + ' h');
    if (minutes) parts.push(minutes + ' min');
    parts.push(remaining + ' s');
    return parts.join(' ');
  };

  const metaFor = (payload, name) => {
    const kpis = payload && payload.meta && payload.meta.kpis;
    return (kpis && kpis[name]) || {};
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

  const setAriaLabel = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.setAttribute('aria-label', value);
  };

  const setFieldError = (input, errorId, message) => {
    if (input) {
      input.classList.toggle('is-invalid', Boolean(message));
      input.setAttribute('aria-invalid', message ? 'true' : 'false');
    }
    setText(errorId, message || '');
    show(errorId, Boolean(message));
  };

  const appendCaption = (table, text) => {
    const caption = document.createElement('caption');
    caption.className = 'visually-hidden';
    caption.textContent = text;
    table.appendChild(caption);
  };

  const renderChartData = (id, rows) => {
    const target = document.getElementById(id);
    if (!target) return;
    target.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement('p');
      empty.className = 'small text-muted mb-0';
      empty.textContent = 'Aucune donnée disponible.';
      target.appendChild(empty);
      return;
    }
    const table = document.createElement('table');
    table.className = 'table table-sm chart-table mb-0';
    appendCaption(table, 'Valeurs du graphique');
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['Libellé', 'Valeur'].forEach(label => {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = label;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    rows.forEach(row => {
      const tr = document.createElement('tr');
      const label = document.createElement('th');
      label.scope = 'row';
      label.textContent = row.label;
      const value = document.createElement('td');
      value.textContent = row.value;
      tr.appendChild(label);
      tr.appendChild(value);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    target.appendChild(table);
  };

  const criticalAlertCount = rows => {
    const values = asArray(rows);
    if (!values.length) return null;
    return values.reduce((sum, row) => sum + numberOr(row && row.count, 0), 0);
  };

  let dashboardPeriodLabel = '7 j';

  const updateAlertState = count => {
    const active = Number.isFinite(count) && count > 0;
    ['alerts-dot', 'alerts-chart-dot', 'alerts-headline-dot', 'alerts-headline', 'alerts-action'].forEach(id => show(id, active));
    if (count === null || !Number.isFinite(count)) {
      setText('alert-status-global', 'Statut des alertes indisponible.');
    } else if (active) {
      setText('alert-status-global', formatInteger(count) + ' alertes critiques sur la période ' + dashboardPeriodLabel + '.');
    } else {
      setText('alert-status-global', 'Aucune alerte critique sur la période ' + dashboardPeriodLabel + '.');
    }
  };

  const chartInstances = {};

  const makeChart = (id, config, hasData, dataId, dataRows) => {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (chartInstances[id]) {
      chartInstances[id].destroy();
      delete chartInstances[id];
    }
    const wrapper = canvas.closest('.chart-wrap');
    const enabled = typeof Chart !== 'undefined';
    renderChartData(dataId, dataRows);
    if (wrapper) {
      let empty = wrapper.querySelector('.chart-empty-message');
      if (!empty) {
        empty = document.createElement('p');
        empty.className = 'chart-empty-message small text-muted';
        wrapper.appendChild(empty);
      }
      empty.textContent = enabled ? 'Aucune donnée disponible pour cette période.' : 'Graphiques indisponibles.';
      wrapper.classList.toggle('chart-empty', !hasData || !enabled);
    }
    if (enabled) chartInstances[id] = new Chart(canvas, config);
  };

  if (typeof Chart !== 'undefined' && Chart.defaults && Chart.defaults.font) {
    Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = '#6e6e73';
    Chart.defaults.borderColor = '#e8e8ed';
    if (Chart.defaults.plugins && Chart.defaults.plugins.legend) {
      Chart.defaults.plugins.legend.labels = Object.assign({}, Chart.defaults.plugins.legend.labels, { boxWidth: 12 });
    }
  }

  const PERIOD_OPTIONS = ['1h', '24h', '7d', '30d', 'custom'];
  let dashboardControlsBound = false;
  let dashboardRequestId = 0;

  const syncDashboardControlsFromUrl = () => {
    const params = new URLSearchParams(window.location.search);
    const value = params.get('period');
    const select = document.getElementById('dashboard-period');
    if (select) {
      select.value = PERIOD_OPTIONS.indexOf(value) >= 0 ? value : '7d';
    }
    const from = document.getElementById('dashboard-from');
    const to = document.getElementById('dashboard-to');
    if (from) from.value = toLocalInput(params.get('from'));
    if (to) to.value = toLocalInput(params.get('to'));
    show('dashboard-custom-range', Boolean(select && select.value === 'custom'));
    setText('dashboard-period-error', '');
    show('dashboard-period-error', false);
  };

  const dashboardParamsFromControls = () => {
    const select = document.getElementById('dashboard-period');
    const values = { period: select && PERIOD_OPTIONS.indexOf(select.value) >= 0 ? select.value : '7d' };
    if (values.period === 'custom') {
      values.from = toIso(document.getElementById('dashboard-from').value);
      values.to = toIso(document.getElementById('dashboard-to').value);
    }
    return values;
  };

  const applyDashboardParams = () => {
    const values = dashboardParamsFromControls();
    if (values.period === 'custom' && (!values.from || !values.to)) {
      setText('dashboard-period-error', 'Renseignez une date de début et une date de fin.');
      show('dashboard-period-error', true);
      return false;
    }
    if (values.from && values.to && values.from >= values.to) {
      setText('dashboard-period-error', 'La date de début doit précéder la date de fin.');
      show('dashboard-period-error', true);
      return false;
    }
    const params = buildQuery(values);
    const suffix = params.toString();
    window.history.replaceState(null, '', window.location.pathname + (suffix ? '?' + suffix : ''));
    setText('dashboard-period-error', '');
    show('dashboard-period-error', false);
    return true;
  };

  const bindDashboardControls = () => {
    const form = document.getElementById('dashboard-period-form');
    const select = document.getElementById('dashboard-period');
    if (dashboardControlsBound || !form || !select) return;
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (applyDashboardParams()) initDashboard();
    });
    select.addEventListener('change', () => show('dashboard-custom-range', select.value === 'custom'));
    dashboardControlsBound = true;
  };

  async function initDashboard() {
    if (!document.getElementById('dashboard-loading')) return;
    const requestId = ++dashboardRequestId;
    const retry = document.getElementById('dashboard-retry');
    if (retry) retry.onclick = () => initDashboard();
    syncDashboardControlsFromUrl();
    bindDashboardControls();
    show('dashboard-loading', true);
    show('dashboard-error', false);
    try {
      const params = buildQuery(dashboardParamsFromControls());
      const data = await fetchJson('/api/v1/stats?' + params.toString());
      if (requestId !== dashboardRequestId) return;
      const temperatures = asArray(data.temperature_avg);
      const alerts = asArray(data.critical_alerts_24h || data.critical_alerts_daily);
      const energy = data.energy_realtime && !Array.isArray(data.energy_realtime) ? data.energy_realtime : {};
      const occupancy = asArray(data.occupancy_rate);
      const maintenance = asArray(data.maintenance_forecast);
      const periodMeta = (data.meta && data.meta.period) || {};
      dashboardPeriodLabel = periodMeta.label || '7 j';
      const periodFrom = formatDate(periodMeta.from, 'date indisponible');
      const periodTo = formatDate(periodMeta.to, 'date indisponible');
      const temperatureMeta = metaFor(data, 'temperature_avg');
      const alertsMeta = metaFor(data, 'critical_alerts_24h');
      const energyMeta = metaFor(data, 'energy_realtime');
      const occupancyMeta = metaFor(data, 'occupancy_rate');
      const maintenanceMeta = metaFor(data, 'maintenance_forecast');
      const temperatureAverage = numberOr(temperatureMeta.global_avg, null);
      const occupancyAverage = numberOr(occupancyMeta.global_avg, null);
      const alertCount = alertsMeta.status === 'no_data' ? null : criticalAlertCount(alerts);
      const energyTotal = numberOr(energy.total_kwh, null);
      const energyHasData = Number.isFinite(energyTotal);
      const energyAge = numberOr(
        energy.age_seconds !== undefined ? energy.age_seconds : energyMeta.age_seconds,
        null
      );
      const energyReading = energy.last_reading_at || energyMeta.last_reading_at;
      const energyUnits = asArray(energy.units);
      const waterUnit = energyUnits.find(unit => String(unit && unit.unit).toLowerCase() === 'm3');
      let energyDetail = 'Aucun relevé kWh sur cette période';
      if (energyHasData) {
        energyDetail = formatNumber(energyTotal) + ' kWh cumulés';
        if (energyReading) {
          energyDetail += ' · dernier relevé : ' + formatDate(energyReading) + ' · il y a ' + formatAge(energyAge);
        }
      }
      if (waterUnit && Number.isFinite(Number(waterUnit.total))) {
        energyDetail += ' · Eau : ' + formatNumber(waterUnit.total) + ' m3';
      }

      setText('dashboard-period-summary', 'Période affichée : ' + dashboardPeriodLabel + ' du ' + periodFrom + ' au ' + periodTo);
      setText('label-temperature', 'Température moyenne · ' + dashboardPeriodLabel);
      setText('label-alerts-text', 'Alertes critiques · ' + dashboardPeriodLabel);
      setText('label-energy', 'Énergie (kWh) · ' + dashboardPeriodLabel);
      setText('label-occupancy', 'Taux d’occupation · ' + dashboardPeriodLabel);
      setText('label-chart-temperature', 'Température moyenne par zone · ' + dashboardPeriodLabel);
      setText('label-chart-alerts-text', 'Alertes critiques · ' + dashboardPeriodLabel);
      setText('label-chart-energy', 'Consommation d’énergie (kWh) · ' + dashboardPeriodLabel);
      setText('label-chart-occupancy', 'Taux d’occupation par salle · ' + dashboardPeriodLabel);
      setAriaLabel('chart-temperature', 'Température moyenne par zone sur ' + dashboardPeriodLabel);
      setAriaLabel('chart-alerts', 'Alertes critiques sur ' + dashboardPeriodLabel);
      setAriaLabel('chart-energy', 'Consommation électrique en kWh sur ' + dashboardPeriodLabel);
      setAriaLabel('chart-occupancy', 'Taux d’occupation moyen par salle sur ' + dashboardPeriodLabel);
      setText('kpi-temperature', Number.isFinite(temperatureAverage) ? formatNumber(temperatureAverage) + ' °C' : 'n/d');
      setText('kpi-alerts', alertCount === null ? 'n/d' : formatInteger(alertCount));
      setText('kpi-energy', energyHasData ? formatNumber(energyTotal) + ' kWh' : 'n/d');
      setText('kpi-occupancy', Number.isFinite(occupancyAverage) ? formatNumber(occupancyAverage) + ' %' : 'n/d');
      setText('kpi-maintenance', maintenanceMeta.status === 'no_data' ? 'n/d' : formatInteger(maintenance.length));
      setText('kpi-temperature-detail', 'Moyenne globale · ' + dashboardPeriodLabel);
      setText('kpi-alerts-detail', 'Fenêtre glissante · ' + dashboardPeriodLabel);
      setText('kpi-energy-detail', energyDetail);
      setText('kpi-occupancy-detail', 'Moyenne globale · ' + dashboardPeriodLabel);
      setText('kpi-maintenance-detail', 'Échéances futures');
      updateAlertState(alertCount);

      const badge = document.getElementById('cache-badge');
      if (badge) {
        const kpiMeta = data.meta && data.meta.kpis ? data.meta.kpis : null;
        const metaValues = kpiMeta ? Object.values(kpiMeta) : [];
        const cachedCount = metaValues.filter(item => item && item.cache_hit).length;
        if (metaValues.length) {
          const complete = cachedCount === metaValues.length;
          badge.textContent = complete
            ? 'Cache : ' + cachedCount + '/' + metaValues.length + ' indicateurs'
            : cachedCount
              ? 'Cache : ' + cachedCount + '/' + metaValues.length + ' indicateurs'
              : 'Cache : données calculées';
          badge.className = 'badge ' + (complete ? 'text-bg-success' : cachedCount ? 'text-bg-info' : 'text-bg-secondary');
        } else {
          badge.textContent = data.cache_hit ? 'Cache : données en cache' : 'Cache : données calculées';
          badge.className = 'badge ' + (data.cache_hit ? 'text-bg-success' : 'text-bg-secondary');
        }
      }

      const hasFinite = values => values.some(value => Number.isFinite(value));
      const axisOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#e8e8ed' }, ticks: { color: '#6e6e73' } },
          y: { beginAtZero: true, grid: { color: '#e8e8ed' }, ticks: { color: '#6e6e73' } }
        }
      };
      const temperatureLabels = temperatures.map(row => cleanLabel(row && row.zone));
      const alertLabels = alerts.map(row => cleanLabel(String((row && row.hour) || (row && row.day) || '').replace('T', ' ').slice(5, 16)));
      const energyBuckets = asArray(energy.buckets).filter(row => String(row && row.unit).toLowerCase() === 'kwh');
      const energyLabels = energyBuckets.map(row => cleanLabel(String((row && row.bucket) || (row && row.minute) || '').replace('T', ' ').slice(0, 16)));
      const occupancyLabels = occupancy.map(row => cleanLabel(row && row.room));
      const maintenanceLabels = maintenance.map(row => cleanLabel(row && row.equipment_id));
      const temperatureValues = temperatures.map(row => numberOr(row && row.avg, null));
      const alertValues = alerts.map(row => numberOr(row && row.count, null));
      const energyValues = energyBuckets.map(row => numberOr(row && row.total, null));
      const occupancyValues = occupancy.map(row => numberOr(row && row.rate, null));
      const maintenanceValues = maintenance.map(row => numberOr(row && row.wear_level, null));
      const chartRows = (labels, values, unit, formatter) => labels.map((label, index) => ({
        label: label,
        value: formatter ? formatter(values[index]) : formatValue(values[index], unit)
      }));

      makeChart('chart-temperature', {
        type: 'bar',
        data: {
          labels: temperatureLabels,
          datasets: [{
            label: 'Température (°C)',
            data: temperatureValues,
            backgroundColor: '#0071e3',
            borderRadius: 6
          }]
        },
        options: Object.assign({}, axisOptions, {
          scales: {
            x: { grid: { color: '#e8e8ed' }, ticks: { color: '#6e6e73' } },
            y: {
              beginAtZero: true,
              grid: { color: '#e8e8ed' },
              ticks: { color: '#6e6e73' },
              title: { display: true, text: '°C' }
            }
          }
        })
      }, hasFinite(temperatureValues), 'chart-temperature-data', chartRows(temperatureLabels, temperatureValues, '°C'));

      makeChart('chart-alerts', {
        type: 'line',
        data: {
          labels: alertLabels,
          datasets: [{
            label: 'Alertes critiques · ' + dashboardPeriodLabel,
            data: alertValues,
            borderColor: '#ff3b30',
            backgroundColor: 'rgba(255, 59, 48, 0.12)',
            pointBackgroundColor: '#ff3b30',
            pointRadius: 2,
            borderWidth: 2,
            fill: true,
            tension: 0.2
          }]
        },
        options: axisOptions
      }, hasFinite(alertValues), 'chart-alerts-data', chartRows(alertLabels, alertValues, '', value => formatInteger(value)));

      makeChart('chart-energy', {
        type: 'line',
        data: {
          labels: energyLabels,
          datasets: [{
            label: 'Énergie (kWh) · ' + dashboardPeriodLabel,
            data: energyValues,
            borderColor: '#34c759',
            backgroundColor: 'rgba(52, 199, 89, 0.12)',
            pointBackgroundColor: '#34c759',
            pointRadius: 2,
            borderWidth: 2,
            fill: true,
            tension: 0.2
          }]
        },
        options: axisOptions
      }, hasFinite(energyValues), 'chart-energy-data', chartRows(energyLabels, energyValues, 'kWh'));

      makeChart('chart-occupancy', {
        type: 'doughnut',
        data: {
          labels: occupancyLabels,
          datasets: [{
            label: 'Taux d’occupation (%)',
            data: occupancyValues,
            backgroundColor: ['#0071e3', '#34c759', '#ff9500', '#8e8e93'],
            borderWidth: 1,
            borderColor: '#ffffff'
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
      }, hasFinite(occupancyValues), 'chart-occupancy-data', chartRows(occupancyLabels, occupancyValues, '%'));

      makeChart('chart-maintenance', {
        type: 'bar',
        data: {
          labels: maintenanceLabels,
          datasets: [{
            label: 'Usure (%)',
            data: maintenanceValues,
            backgroundColor: '#ff9500',
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
          scales: {
            x: {
              beginAtZero: true,
              max: 100,
              grid: { color: '#e8e8ed' },
              ticks: { color: '#6e6e73' }
            },
            y: { grid: { display: false }, ticks: { color: '#6e6e73' } }
          }
        }
      }, hasFinite(maintenanceValues), 'chart-maintenance-data', maintenanceLabels.map((label, index) => {
        const row = maintenance[index] || {};
        return {
          label: label,
          value: formatValue(maintenanceValues[index], '%') + ' · ' + formatDate(row.estimated_due_date)
        };
      }));

      const maintenanceBody = document.getElementById('maintenance-body');
      if (maintenanceBody) {
        maintenanceBody.replaceChildren();
        maintenance.forEach(row => {
          const item = row || {};
          const wear = numberOr(item.wear_level, null);
          const tr = document.createElement('tr');
          [
            cleanLabel(item.equipment_id),
            item.predicted_failure === true ? 'Oui' : item.predicted_failure === false ? 'Non' : 'n/d',
            Number.isFinite(wear) ? formatNumber(wear, 0) + ' %' : 'n/d',
            formatDate(item.estimated_due_date, 'Échéance indisponible')
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
      if (requestId !== dashboardRequestId) return;
      setText('dashboard-error-message', ' ' + error.message);
      show('dashboard-error', true);
      ['kpi-temperature', 'kpi-alerts', 'kpi-energy', 'kpi-occupancy', 'kpi-maintenance'].forEach(id => setText(id, 'Indisponible'));
      ['kpi-temperature-detail', 'kpi-alerts-detail', 'kpi-energy-detail', 'kpi-occupancy-detail', 'kpi-maintenance-detail'].forEach(id => setText(id, 'Indisponible'));
      updateAlertState(null);
    } finally {
      if (requestId === dashboardRequestId) show('dashboard-loading', false);
    }
  }

  const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;

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
      if (!file) {
        selected = null;
        setText('upload-file-name', 'Aucun fichier sélectionné');
        setBusy(false);
        return;
      }
      if (!allowed.test(file.name)) {
        selected = null;
        input.value = '';
        setText('upload-file-name', 'Format non accepté : ' + file.name);
        setError('Formats autorisés : .csv, .json et .txt.');
        setBusy(false);
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        selected = null;
        input.value = '';
        setText('upload-file-name', 'Fichier trop volumineux : ' + file.name);
        setError('Taille maximale : 100 Mo.');
        setBusy(false);
        return;
      }
      selected = file;
      setText('upload-file-name', file.name + ' · ' + formatNumber(file.size / 1024 / 1024) + ' Mo');
      setBusy(false);
    };

    zone.addEventListener('keydown', event => {
      if (event.target !== zone || (event.key !== 'Enter' && event.key !== ' ')) return;
      event.preventDefault();
      input.click();
    });
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
        if (wrapper) {
          wrapper.setAttribute('aria-valuenow', String(value));
          wrapper.setAttribute('aria-valuetext', value + ' %');
        }
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
          setText('upload-file-id', result.file_id || 'Identifiant indisponible');
          setText('upload-result-meta', [
            result.log_type ? 'Type : ' + result.log_type : '',
            result.logs_count !== undefined ? formatInteger(result.logs_count) + ' lignes' : '',
            result.status ? 'Statut : ' + result.status : ''
          ].filter(Boolean).join(' · '));
          show('upload-result', true);
          initUploadHistory();
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

  let uploadHistoryTimer = null;

  const formatFileSize = value => {
    const bytes = Number(value);
    if (!Number.isFinite(bytes)) return 'Taille indisponible';
    if (bytes < 1024) return bytes + ' o';
    if (bytes < 1024 * 1024) return formatNumber(bytes / 1024) + ' Ko';
    return formatNumber(bytes / 1024 / 1024) + ' Mo';
  };

  const uploadStatusCell = row => {
    const cell = document.createElement('td');
    const status = String((row && row.status) || '').trim();
    if (!status) {
      cell.textContent = 'Statut indisponible';
      return cell;
    }
    const badge = document.createElement('span');
    const classes = {
      indexed: 'text-bg-success',
      failed: 'text-bg-danger',
      ingesting: 'text-bg-info',
      validated: 'text-bg-secondary'
    };
    badge.className = 'badge ' + (classes[status] || 'text-bg-secondary');
    badge.textContent = status;
    cell.appendChild(badge);
    if (row.error_message) {
      const error = document.createElement('div');
      error.className = 'small text-danger mt-1';
      error.textContent = String(row.error_message);
      cell.appendChild(error);
    }
    return cell;
  };

  async function initUploadHistory() {
    const list = document.getElementById('upload-history-list');
    if (!list) return;
    const retry = document.getElementById('upload-history-retry');
    if (retry && retry.dataset.bound !== '1') {
      retry.addEventListener('click', () => initUploadHistory());
      retry.dataset.bound = '1';
    }
    if (uploadHistoryTimer) {
      window.clearTimeout(uploadHistoryTimer);
      uploadHistoryTimer = null;
    }
    try {
      const data = await fetchJson('/api/v1/files?size=10');
      const rows = asArray(data.files);
      list.replaceChildren();
      if (!rows.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 7;
        cell.className = 'text-muted small';
        cell.textContent = 'Aucun fichier déposé.';
        row.appendChild(cell);
        list.appendChild(row);
      }
      rows.forEach(entry => {
        const item = entry || {};
        const row = document.createElement('tr');
        const name = document.createElement('td');
        name.className = 'small fw-semibold';
        name.textContent = cleanLabel(item.original_name);
        row.appendChild(name);
        const type = document.createElement('td');
        type.className = 'small';
        type.textContent = item.log_type || 'Non renseigné';
        row.appendChild(type);
        const size = document.createElement('td');
        size.className = 'small';
        size.textContent = formatFileSize(item.size_bytes);
        row.appendChild(size);
        const lines = document.createElement('td');
        lines.className = 'small';
        const count = item.indexed_count !== undefined ? item.indexed_count : item.logs_count;
        lines.textContent = formatInteger(count) === 'n/d' ? 'Non disponible' : formatInteger(count);
        row.appendChild(lines);
        row.appendChild(uploadStatusCell(item));
        const uploaded = document.createElement('td');
        uploaded.className = 'small text-muted';
        uploaded.textContent = formatDate(item.uploaded_at, 'Date indisponible');
        row.appendChild(uploaded);
        const details = document.createElement('td');
        const link = document.createElement('a');
        link.className = 'small';
        link.href = '/api/v1/files/' + encodeURIComponent(item.file_id || '');
        link.textContent = 'JSON';
        details.appendChild(link);
        row.appendChild(details);
        list.appendChild(row);
      });
      setText('upload-history-status', formatInteger(data.total) + ' fichier(s) déposé(s)');
      if (rows.some(item => ['validated', 'ingesting'].indexOf(String(item && item.status)) >= 0)) {
        uploadHistoryTimer = window.setTimeout(() => initUploadHistory(), 10000);
      }
    } catch (error) {
      list.replaceChildren();
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 7;
      cell.className = 'text-danger small';
      cell.textContent = 'Historique indisponible.';
      row.appendChild(cell);
      list.appendChild(row);
      setText('upload-history-status', error.message);
    }
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
          row.results_count !== undefined ? formatInteger(row.results_count) + ' document(s)' : '',
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

  function initSuggestions() {
    const form = document.getElementById('search-form');
    const input = document.getElementById('q');
    const list = document.getElementById('suggest-list');
    if (!form || !input || !list || typeof AbortController === 'undefined') return;

    let timer = null;
    let controller = null;
    let requestId = 0;
    let active = -1;
    let items = [];

    const hide = () => {
      list.replaceChildren();
      list.classList.add('d-none');
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      setText('suggest-status', '');
      active = -1;
      items = [];
    };

    const cancel = () => {
      if (timer) window.clearTimeout(timer);
      timer = null;
      if (controller) controller.abort();
      controller = null;
      requestId += 1;
      hide();
    };

    const setActive = index => {
      const options = Array.from(list.querySelectorAll('[role="option"]'));
      if (!options.length) return;
      active = (index + options.length) % options.length;
      options.forEach((option, optionIndex) => {
        const selected = optionIndex === active;
        option.classList.toggle('active', selected);
        option.setAttribute('aria-selected', String(selected));
      });
      input.setAttribute('aria-activedescendant', options[active].id);
    };

    const select = index => {
      const item = items[index];
      if (!item) return;
      input.value = String(item.value || '');
      cancel();
      input.focus();
    };

    const render = suggestions => {
      items = asArray(suggestions).slice(0, 8);
      list.replaceChildren();
      active = -1;
      if (!items.length) {
        hide();
        setText('suggest-status', 'Aucune valeur proposée.');
        return;
      }
      items.forEach((item, index) => {
        const option = document.createElement('li');
        option.id = 'suggest-option-' + index;
        option.className = 'list-group-item list-group-item-action suggest-item py-2';
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', 'false');
        const value = document.createElement('div');
        value.className = 'small fw-semibold';
        value.textContent = String(item.value || '');
        const meta = document.createElement('div');
        meta.className = 'small text-muted suggest-meta';
        meta.textContent = (item.field || 'valeur') + ' · ' + formatInteger(item.count) + ' document(s)';
        option.appendChild(value);
        option.appendChild(meta);
        option.addEventListener('mousedown', event => {
          event.preventDefault();
          select(index);
        });
        list.appendChild(option);
      });
      list.classList.remove('d-none');
      input.setAttribute('aria-expanded', 'true');
      setText('suggest-status', items.length + ' valeur(s) proposée(s).');
    };

    const fetchSuggestions = async term => {
      const id = ++requestId;
      controller = new AbortController();
      const params = buildQuery({
        q: term,
        log_type: form.elements.log_type.value,
        from: toIso(form.elements.from.value),
        to: toIso(form.elements.to.value),
        severity: form.elements.severity.value,
        zone: form.elements.zone.value,
        entity_id: form.elements.entity_id.value
      });
      params.set('size', '8');
      try {
        const payload = await fetchJson('/api/v1/suggest?' + params.toString(), {
          signal: controller.signal,
          cache: 'no-store'
        });
        if (id !== requestId) return;
        render(payload.suggestions);
      } catch (error) {
        if (id === requestId && error.name !== 'AbortError') hide();
      }
    };

    input.addEventListener('input', () => {
      if (timer) window.clearTimeout(timer);
      if (controller) controller.abort();
      controller = null;
      const term = input.value.trim();
      if (term.length < 2) {
        requestId += 1;
        hide();
        return;
      }
      timer = window.setTimeout(() => fetchSuggestions(term), 250);
    });

    input.addEventListener('keydown', event => {
      if (list.classList.contains('d-none')) return;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActive(active + 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActive(active - 1);
      } else if (event.key === 'Enter' && active >= 0) {
        event.preventDefault();
        select(active);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        cancel();
      }
    });

    input.addEventListener('blur', () => {
      if (!list.contains(document.activeElement)) cancel();
    });
    form.addEventListener('submit', cancel);
  }

  function initSearch() {
    const form = document.getElementById('search-form');
    if (!form) return;
    form.addEventListener('submit', event => {
      event.preventDefault();
      const values = new FormData(form);
      const fromInput = document.getElementById('from');
      const toInput = document.getElementById('to');
      const fromValue = String(values.get('from') || '');
      const toValue = String(values.get('to') || '');
      const fromTime = fromValue ? new Date(fromValue).getTime() : null;
      const toTime = toValue ? new Date(toValue).getTime() : null;
      if (fromTime !== null && Number.isNaN(fromTime)) {
        setFieldError(fromInput, 'date-error', 'La date de début est invalide.');
        if (fromInput) fromInput.focus();
        return;
      }
      if (toTime !== null && Number.isNaN(toTime)) {
        setFieldError(toInput, 'date-error', 'La date de fin est invalide.');
        if (toInput) toInput.focus();
        return;
      }
      if (fromTime !== null && toTime !== null && fromTime > toTime) {
        setFieldError(toInput, 'date-error', 'La date de fin doit être postérieure à la date de début.');
        if (toInput) toInput.focus();
        return;
      }
      setFieldError(fromInput, 'date-error', '');
      setFieldError(toInput, 'date-error', '');
      const query = String(values.get('q') || '').trim();
      const queryInput = document.getElementById('q');
      if (query.length === 1) {
        setFieldError(queryInput, 'q-error', 'Saisissez au moins 2 caractères.');
        if (queryInput) queryInput.focus();
        return;
      }
      setFieldError(queryInput, 'q-error', '');
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
    initSuggestions();
    initHistory();
  }

  async function initResults() {
    const body = document.getElementById('results-body');
    if (!body) return;

    const retry = document.getElementById('results-retry');
    if (retry) retry.onclick = () => window.location.reload();

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
      setText('results-count', rows.length + ' document(s) affiché(s)');
      const totalPages = Math.max(1, Math.ceil(Number(data.total || 0) / size));
      setText('page-label', 'Page ' + current + ' sur ' + totalPages);

      const appendCell = (tr, value) => {
        const td = document.createElement('td');
        td.textContent = value === null || value === undefined || value === '' ? 'n/d' : String(value);
        tr.appendChild(td);
        return td;
      };

      body.replaceChildren();
      if (!rows.length) {
        const tr = document.createElement('tr');
        const td = appendCell(tr, 'Aucun document pour ces critères.');
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
          const severityCell = appendCell(tr, row.severity);
          if (String(row.severity || '').toLowerCase() === 'critical') {
            severityCell.classList.add('severity-critical');
            const dot = document.createElement('span');
            dot.className = 'status-dot status-dot-inline';
            dot.setAttribute('aria-hidden', 'true');
            severityCell.prepend(dot);
          }

          const actionCell = appendCell(tr, '');
          actionCell.className = 'text-end';
          const detailId = 'detail-' + index;
          const toggle = document.createElement('button');
          toggle.type = 'button';
          toggle.className = 'btn btn-sm btn-outline-primary';
          toggle.textContent = 'Détails';
          toggle.setAttribute('aria-label', 'Afficher les détails du document ' + (index + 1));
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
          pre.tabIndex = 0;
          pre.setAttribute('aria-label', 'Données JSON du document ' + (index + 1));
          pre.textContent = JSON.stringify(row, null, 2);
          detailCell.appendChild(pre);
          detailRow.appendChild(detailCell);
          body.appendChild(detailRow);

          toggle.addEventListener('click', () => {
            const hidden = detailRow.classList.toggle('d-none');
            toggle.setAttribute('aria-expanded', String(!hidden));
            toggle.textContent = hidden ? 'Détails' : 'Masquer';
            toggle.setAttribute('aria-label', (hidden ? 'Afficher' : 'Masquer') + ' les détails du document ' + (index + 1));
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

  async function initNavAlerts() {
    if (document.getElementById('dashboard-loading')) return;
    try {
      const data = await fetchJson('/api/v1/stats');
      const alertsMeta = metaFor(data, 'critical_alerts_24h');
      const alerts = asArray(data.critical_alerts_24h || data.critical_alerts_daily);
      updateAlertState(alertsMeta.status === 'no_data' ? null : criticalAlertCount(alerts));
    } catch (error) {
      setText('alert-status-global', 'Statut des alertes indisponible.');
    }
  }

  const start = () => {
    initDashboard();
    initNavAlerts();
    initUpload();
    initUploadHistory();
    initSearch();
    initResults();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
