const form = document.querySelector('#scrape-form');
const input = document.querySelector('#ico');
const button = document.querySelector('#submit');
const statusEl = document.querySelector('#status');
const tabs = document.querySelector('#tabs');
const results = document.querySelector('#results');
const sourceInputs = Array.from(document.querySelectorAll('input[name="source"]'));
const crzOptions = document.querySelector('#crz-options');
const crzKeepLegalFormInput = document.querySelector('#crz-keep-legal-form');
let latestRawJson = '';
let latestData = null;

const downloadIcon = `
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
    <path d="M7 10l5 5 5-5"></path>
    <path d="M12 15V3"></path>
  </svg>
`;

const copyIcon = `
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect>
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path>
  </svg>
`;

const categoryLabels = {
  ico: 'Všeob. Info',
  orsr: 'ORSR',
  rpvs: 'RPVS',
  finstat: 'FinStat',
  ruz: 'RÚZ',
  crz: 'CRZ',
  raw: 'Export dát',
  obchodne_meno: 'Obchodné meno',
  sidlo: 'Sídlo',
  den_zapisu: 'Deň zápisu',
  pravna_forma: 'Právna forma',
  predmet_podnikania: 'Predmet podnikania',
  vyska_zakladneho_imania: 'Výška základného imania',
  datum_aktualizacie_dat: 'Dátum aktualizácie dát',
  typ_organu: 'Typ orgánu',
  statutarny_organ: 'Štatutárny orgán',
  pravny_predchodca: 'Právny predchodca',
  konanie_menom_spolocnosti: 'Konanie menom spoločnosti',
  dozorna_rada: 'Dozorná rada',
  akcionar: 'Akcionár',
  dalsie_pravne_skutocnosti: 'Ďalšie právne skutočnosti',
  partner_verejneho_sektora: 'Partner verejného sektora',
  opravnena_osoba: 'Oprávnená osoba',
  konecni_uzivatelia_vyhod: 'Koneční užívatelia výhod',
  oznamenie_o_overeni_konecnych_uzivatelov_vyhod: 'Oznámenie o overení konečných užívateľov výhod',
  zakladne_udaje: 'Základné údaje',
  financne_ukazovatele: 'Finančné ukazovatele',
  dolezite_ukazovatele: 'Dôležité ukazovatele',
  grafy: 'Grafy',
  uctovne_zavierky: 'Účtovné závierky',
  vyrocne_spravy: 'Výročné správy',
  zaznamy: 'Záznamy',
  dokumenty: 'Dokumenty',
  nazov: 'Názov',
  typ: 'Typ',
  zdroj: 'Zdroj',
  url: 'URL',
  zmluvy: 'Zmluvy',
  datum: 'Dátum',
  nazov_zmluvy: 'Názov zmluvy',
  cislo_zmluvy: 'Číslo zmluvy',
  link: 'Odkaz',
  cena: 'Cena',
  dodavatel: 'Dodávateľ',
  odberatel: 'Odberateľ',
  vyhladavanie_podla: 'Vyhľadávanie podľa',
  hladany_dodavatel: 'Hľadaný dodávateľ',
  nazov_suboru: 'Názov súboru',
  podnazov: 'Podnázov',
  chart_data: 'Dáta grafu',
  value_label: 'Hodnota',
  total_label: 'Celková hodnota',
  total_value: 'Celková hodnota',
  rok: 'Rok',
  farba: 'Farba',
  body: 'Dáta',
  legend: 'Legenda'
};

function formatKey(key) {
  if (categoryLabels[key]) return categoryLabels[key];
  const label = String(key).replaceAll('_', ' ');
  return label.charAt(0).toLocaleUpperCase('sk-SK') + label.slice(1);
}

function selectedSources() {
  return sourceInputs
    .filter(input => input.checked)
    .map(input => input.value);
}

function syncCrzOptionsVisibility() {
  const crzSelected = sourceInputs.some(input => input.value === 'crz' && input.checked);
  crzOptions.hidden = !crzSelected;
}

function clearResults(message = 'Výsledky sa zobrazia po vyhľadaní IČO.') {
  latestData = null;
  tabs.className = 'tabs';
  tabs.innerHTML = '';
  results.innerHTML = `<div class="empty-state">${message}</div>`;
}

function containsUnavailableInfo(value) {
  return JSON.stringify(value || '').includes('Informácia nedostupná');
}

function renderValue(value) {
  if (value === null || value === undefined || value === '') {
    return '<span>-</span>';
  }

  if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 1 && value.message) {
    return `<div class="notice">${renderValue(value.message)}</div>`;
  }

  if (typeof value === 'object' && !Array.isArray(value) && value.image) {
    return `
      <article class="finstat-graph">
        <h4 class="finstat-graph-title">${renderValue(value.nazov || 'Graf')}</h4>
        <img src="${escapeAttribute(value.image)}" alt="${escapeAttribute(value.nazov || 'FinStat graf')}" loading="lazy" />
      </article>
    `;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return '<span>-</span>';
    return `<div class="list">${value.map(item => `
      <div class="list-item">${renderValue(item)}</div>
    `).join('')}</div>`;
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value).filter(([key]) => key !== '__source_url');
    if (entries.length === 0) return '<span>-</span>';
    return `<div class="field-grid nested">${entries.map(([key, child]) => `
      <div class="field-label">${formatKey(key)}</div>
      <div class="field-value">
        ${renderValue(child)}
        ${key === 'dolezite_ukazovatele' && containsUnavailableInfo(child)
          ? '<div class="field-note">Informácie sú nedostupné kvôli free verzii Finstatu.</div>'
          : ''}
      </div>
    `).join('')}</div>`;
  }

  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function escapeAttribute(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}


function firstValue(...values) {
  for (const value of values) {
    if (value !== null && value !== undefined && String(value).trim() !== '') {
      return value;
    }
  }
  return '-';
}

function renderSummary(data) {
  const orsr = data.orsr || {};
  const finstat = data.finstat || {};
  const finstatBasic = finstat.zakladne_udaje || {};
  const companyName = firstValue(orsr.obchodne_meno, finstatBasic['Obchodné meno'], finstatBasic.Názov);
  const address = firstValue(orsr.sidlo, finstatBasic['Sídlo'], finstatBasic.Adresa);
  const foundingDay = firstValue(orsr.den_zapisu, finstatBasic['Dátum vzniku']);

  return `
    <section class="summary-layout">
      <div class="field-grid">
        <div class="field-label">IČO</div>
        <div class="field-value">${renderValue(data.ico)}</div>
        <div class="field-label">Názov spoločnosti</div>
        <div class="field-value">${renderValue(companyName)}</div>
        <div class="field-label">Adresa</div>
        <div class="field-value">${renderValue(address)}</div>
        <div class="field-label">Deň vzniku</div>
        <div class="field-value">${renderValue(foundingDay)}</div>
      </div>
      ${'finstat' in data ? renderFinstatGraphs(finstat.grafy || []) : ''}
    </section>
  `;
}

function renderFinstatLineChart(chartData) {
  const points = chartData && Array.isArray(chartData.body) ? chartData.body : [];
  if (points.length < 2) return '';

  const width = 520;
  const height = 260;
  const padding = { top: 28, right: 30, bottom: 44, left: 34 };
  const xs = points.map((point, index) => Number.isFinite(point.x_svg) ? point.x_svg : index);
  const ys = points.map(point => Number.isFinite(point.y_svg) ? point.y_svg : 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const scaleX = value => padding.left + ((value - minX) / Math.max(maxX - minX, 1)) * plotWidth;
  const scaleY = value => padding.top + ((value - minY) / Math.max(maxY - minY, 1)) * plotHeight;
  const chartPoints = points.map((point, index) => ({
    x: scaleX(xs[index]),
    y: scaleY(ys[index]),
    year: point.rok || '',
    valueLabel: point.value_label || '',
    valueEstimated: Boolean(point.value_estimated)
  }));
  const linePath = chartPoints.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');
  const gridLines = [0, 0.33, 0.66, 1].map(ratio => padding.top + ratio * plotHeight);

  return `
    <svg class="line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttribute(chartData.nazov || 'FinStat graf')}">
      ${gridLines.map(y => `<line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}" stroke="#e6e5e5" stroke-dasharray="6 4" />`).join('')}
      <path class="chart-line" d="${linePath}" />
      ${chartPoints.map(point => `
        <circle class="chart-point" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4" />
        ${point.valueLabel ? `<text class="value-label ${point.valueEstimated ? 'estimated' : ''}" x="${point.x.toFixed(1)}" y="${Math.max(14, point.y - 10).toFixed(1)}" text-anchor="middle">${renderValue(point.valueLabel)}</text>` : ''}
        <text x="${point.x.toFixed(1)}" y="${height - 16}" text-anchor="middle">${renderValue(point.year)}</text>
      `).join('')}
    </svg>
  `;
}

function renderFinstatBarChart(chartData) {
  const rows = chartData && Array.isArray(chartData.body) ? chartData.body : [];
  const legend = chartData && Array.isArray(chartData.legend) ? chartData.legend : [];
  if (rows.length === 0 || legend.length === 0) return '';

  const width = 760;
  const height = 340;
  const padding = { top: 34, right: 28, bottom: 48, left: 34 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxStack = Math.max(...rows.map(row => Number(row.stack_height_svg) || 0), 1);
  const barWidth = Math.min(76, plotWidth / Math.max(rows.length, 1) * 0.6);
  const gap = rows.length > 1 ? plotWidth / (rows.length - 1) : 0;
  const gridLines = [0, 0.33, 0.66, 1].map(ratio => padding.top + ratio * plotHeight);

  const bars = rows.map((row, rowIndex) => {
    const centerX = rows.length > 1 ? padding.left + rowIndex * gap : padding.left + plotWidth / 2;
    let currentBottom = padding.top + plotHeight;
    const segments = Array.isArray(row.segments)
      ? row.segments.filter(segment => (Number(segment.height_svg) || 0) > 0)
      : [];
    const rects = [...segments].reverse().map(segment => {
      const segmentHeight = Math.max(1, ((Number(segment.height_svg) || 0) / maxStack) * plotHeight);
      const y = currentBottom - segmentHeight;
      currentBottom = y;
      return `<rect x="${(centerX - barWidth / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${segmentHeight.toFixed(1)}" fill="${escapeAttribute(segment.color || '#52606d')}" />`;
    }).join('');

    return `
      ${rects}
      ${row.total_label ? `<text class="total-label" x="${centerX.toFixed(1)}" y="${Math.max(14, currentBottom - 8).toFixed(1)}" text-anchor="middle">${renderValue(row.total_label)}</text>` : ''}
      <text x="${centerX.toFixed(1)}" y="${height - 16}" text-anchor="middle">${renderValue(row.rok || '')}</text>
    `;
  }).join('');

  return `
    <div class="bar-chart-layout">
      <svg class="bar-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttribute(chartData.nazov || 'FinStat stĺpcový graf')}">
        ${gridLines.map(y => `<line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}" stroke="#e6e5e5" stroke-dasharray="6 4" />`).join('')}
        ${bars}
      </svg>
      <div class="chart-legend" aria-label="Legenda grafu">
        ${legend.map(item => `
          <div class="chart-legend-item">
            <span class="chart-legend-swatch" style="background:${escapeAttribute(item.color || '#52606d')}"></span>
            <span>${renderValue(item.label || '')}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderFinstatPieChart(chartData) {
  const slices = chartData && Array.isArray(chartData.body) ? chartData.body : [];
  if (slices.length === 0) return '';

  return `
    <div class="pie-chart-layout">
      <svg class="pie-chart" viewBox="0 0 284 230" role="img" aria-label="${escapeAttribute(chartData.nazov || 'FinStat koláčový graf')}" preserveAspectRatio="xMidYMid meet">
        ${slices.map(slice => slice.path ? `<path d="${escapeAttribute(slice.path)}" fill="${escapeAttribute(slice.color || '#52606d')}" transform="translate(4,67) scale(1.08) translate(-11,-7)" />` : '').join('')}
      </svg>
      <div class="pie-legend" aria-label="Legenda grafu">
        ${slices.map(slice => `
          <div class="pie-legend-item">
            <span class="chart-legend-swatch" style="background:${escapeAttribute(slice.color || '#52606d')}"></span>
            <span>${renderValue(slice.label || '')}</span>
            <span class="pie-legend-value">${renderValue(slice.value_label || '')}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderFinstatChart(chartData) {
  if (!chartData || typeof chartData !== 'object') return '';
  if (chartData.typ === 'bar') return renderFinstatBarChart(chartData);
  if (chartData.typ === 'pie') return renderFinstatPieChart(chartData);
  return renderFinstatLineChart(chartData);
}

function renderFinstatGraph(graph, index) {
  const title = graph.nazov || (graph.chart_data && graph.chart_data.nazov) || `Graf ${index + 1}`;
  const isWide = graph.chart_data && graph.chart_data.typ === 'bar';
  const chart = graph.chart_data ? renderFinstatChart(graph.chart_data) : '';
  const fallbackImage = graph.image
    ? `<img src="${escapeAttribute(graph.image)}" alt="${escapeAttribute(title)}" loading="lazy" />`
    : '';

  return `
    <article class="finstat-graph ${isWide ? 'wide' : ''}">
      <h4 class="finstat-graph-title">${renderValue(title)}</h4>
      ${chart || fallbackImage || '<div class="notice">Graf sa nepodarilo vykresliť.</div>'}
    </article>
  `;
}

function renderFinstatGraphs(graphs) {
  if (!Array.isArray(graphs) || graphs.length === 0) {
    return '<div class="notice">FinStat grafy sa nepodarilo načítať.</div>';
  }

  return `
    <section class="finstat-graphs" aria-label="FinStat grafy">
      <h3 class="finstat-graphs-title">FinStat grafy</h3>
      <div class="finstat-graph-list">
        ${graphs.map((graph, index) => renderFinstatGraph(graph, index)).join('')}
      </div>
    </section>
  `;
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  textarea.remove();
}

function exportFilename() {
  const ico = input.value.trim() || 'export';
  return `ico-scraper-${ico}.json`;
}

function downloadJson() {
  const blob = new Blob([latestRawJson], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = exportFilename();
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function downloadXlsx() {
  if (!latestData) return;

  const response = await fetch('/export/xlsx', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(latestData)
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Export do XLSX zlyhal.');
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = exportFilename().replace(/\.json$/, '.xlsx');
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function bindExportButtons() {
  const downloadButton = document.querySelector('#download-export');
  const downloadXlsxButton = document.querySelector('#download-xlsx');
  const copyButton = document.querySelector('#copy-export');

  if (downloadButton) {
    downloadButton.addEventListener('click', downloadJson);
  }

  if (downloadXlsxButton) {
    downloadXlsxButton.addEventListener('click', async () => {
      try {
        await downloadXlsx();
      } catch (error) {
        statusEl.className = 'status error';
        statusEl.textContent = error.message;
      }
    });
  }

  if (copyButton) {
    copyButton.addEventListener('click', async () => {
      try {
        await copyText(latestRawJson);
        const originalHtml = copyButton.innerHTML;
        copyButton.textContent = 'Skopírované';
        setTimeout(() => { copyButton.innerHTML = originalHtml; }, 1600);
      } catch (error) {
        statusEl.className = 'status error';
        statusEl.textContent = 'Kopírovanie zlyhalo.';
      }
    });
  }
}




function renderCrz(value) {
  if (!value || value.message) {
    return renderValue(value);
  }

  const contracts = Array.isArray(value.zmluvy) ? value.zmluvy : [];
  if (contracts.length === 0) {
    return '<div class="notice">V CRZ sa nepodarilo načítať zmluvy.</div>';
  }

  return `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Dátum</th>
            <th>Zmluva</th>
            <th>Cena</th>
            <th>Dodávateľ</th>
            <th>Odberateľ</th>
          </tr>
        </thead>
        <tbody>
          ${contracts.map(contract => `
            <tr>
              <td>${renderValue(contract.datum || '-')}</td>
              <td>
                ${contract.link ? `<a class="document-link" href="${escapeAttribute(contract.link)}" target="_blank" rel="noopener noreferrer">${renderValue(contract.nazov_zmluvy || '-')}</a>` : renderValue(contract.nazov_zmluvy || '-')}
                ${contract.cislo_zmluvy ? `<br><span>${renderValue(contract.cislo_zmluvy)}</span>` : ''}
              </td>
              <td>${renderValue(contract.cena || '-')}</td>
              <td>${renderValue(contract.dodavatel || '-')}</td>
              <td>${renderValue(contract.odberatel || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderRuzRecordsTable(records, tableId) {
  if (!Array.isArray(records) || records.length === 0) {
    return '<div class="notice">Záznamy sa nepodarilo načítať.</div>';
  }

  const typeColumn = records.some(record => Object.prototype.hasOwnProperty.call(record, 'Typ výročnej správy'))
    ? 'Typ výročnej správy'
    : 'Typ závierky';
  const columns = ['Obdobie', typeColumn, 'Predložená dňa', 'Zostavená dňa', 'Schválená dňa', 'SA uložená dňa'];
  return `
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>${columns.map(column => `<th>${renderValue(column)}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${records.map((record, index) => `
            <tr>
              ${columns.map((column, columnIndex) => `
                <td>
                  ${columnIndex === 0
                    ? `<button class="period-button" type="button" data-documents-toggle="${tableId}-${index}" aria-expanded="false">${renderValue(record[column] || '-')}</button>`
                    : renderValue(record[column] || '-')}
                </td>
              `).join('')}
            </tr>
            <tr class="documents-row" data-documents-row="${tableId}-${index}">
              <td class="documents-cell" colspan="${columns.length}">
                ${renderDocumentsTable(record.dokumenty || [])}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderDocumentsTable(documents) {
  if (!Array.isArray(documents) || documents.length === 0) {
    return '<div class="notice">Pre tento záznam nie sú dostupné dokumenty.</div>';
  }

  return `
    <p class="documents-title">Dokumenty</p>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Názov</th>
            <th>Typ</th>
            <th>Zdroj</th>
          </tr>
        </thead>
        <tbody>
          ${documents.map(documentItem => `
            <tr>
              <td>${documentItem.url ? `<a class="document-link" href="${escapeAttribute(documentItem.url)}" target="_blank" rel="noopener noreferrer">${renderValue(documentItem.nazov || '-')}</a>` : renderValue(documentItem.nazov || '-')}</td>
              <td>${renderValue(documentItem.typ || '-')}</td>
              <td>${renderValue(documentItem.zdroj || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function bindRuzTables() {
  document.querySelectorAll('[data-documents-toggle]').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const row = document.querySelector(`[data-documents-row="${toggle.dataset.documentsToggle}"]`);
      if (!row) return;
      const isVisible = row.classList.toggle('visible');
      toggle.setAttribute('aria-expanded', isVisible ? 'true' : 'false');
    });
  });
}

function renderSourceAttribution(value) {
  if (!value || typeof value !== 'object' || !value.__source_url || value.message) {
    return '';
  }

  const url = value.__source_url;
  return `
    <div class="source-attribution">
      Informácie boli vytiahnuté zo zdroja:
      <a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${renderValue(url)}</a>
    </div>
  `;
}

function stripSourceMetadata(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return value;
  }
  return Object.fromEntries(Object.entries(value).filter(([key]) => key !== '__source_url'));
}

function renderRpvs(value) {
  if (!value || value.message) {
    return renderValue(value);
  }

  const partner = value.partner_verejneho_sektora || {};
  const rest = Object.fromEntries(
    Object.entries(value).filter(([key]) => key !== 'partner_verejneho_sektora')
  );
  const partnerBlock = partner && Object.keys(partner).length > 0 ? renderValue(partner) : '';
  const restBlock = rest && Object.keys(rest).length > 0 ? renderValue(rest) : '';

  return `${partnerBlock}${restBlock}`;
}

function renderRuz(value) {
  if (!value || value.message) {
    return renderValue(value);
  }

  const statements = Array.isArray(value.uctovne_zavierky)
    ? value.uctovne_zavierky
    : Array.isArray(value.zaznamy) ? value.zaznamy : [];
  const annualReports = Array.isArray(value.vyrocne_spravy) ? value.vyrocne_spravy : [];
  const rest = Object.fromEntries(
    Object.entries(value).filter(([key]) => !['zaznamy', 'uctovne_zavierky', 'vyrocne_spravy'].includes(key))
  );

  return `
    ${renderValue(rest)}
    <h3 class="section-subtitle">Účtovné závierky</h3>
    ${renderRuzRecordsTable(statements, 'statements')}
    <h3 class="section-subtitle">Výročné správy</h3>
    ${renderRuzRecordsTable(annualReports, 'annual-reports')}
  `;
}

function renderPanel(key, value, active) {
  if (key === 'raw') {
    return `
      <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
        <h2 class="panel-title">Export dát</h2>
        <div class="export-panel">
          <p>Stiahnite si kompletný výsledok vo formáte JSON.</p>
          <div class="export-actions">
            <button class="export-button" id="download-export" type="button">${downloadIcon} Stiahnuť .json</button>
            <button class="export-button" id="download-xlsx" type="button">${downloadIcon} Stiahnuť .xlsx</button>
            <button class="export-button secondary" id="copy-export" type="button">${copyIcon} Kopírovať JSON</button>
          </div>
        </div>
      </section>
    `;
  }

  if (key === 'ico') {
    return `
      <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
        <h2 class="panel-title">Všeobecné Informácie</h2>
        ${renderSummary(value)}
      </section>
    `;
  }

  const attribution = renderSourceAttribution(value);
  const metadataFreeValue = stripSourceMetadata(value);
  const displayValue = key === 'finstat' && metadataFreeValue && typeof metadataFreeValue === 'object'
    ? Object.fromEntries(Object.entries(metadataFreeValue).filter(([childKey]) => childKey !== 'grafy'))
    : metadataFreeValue;
  const body = key === 'rpvs'
    ? renderRpvs(displayValue)
    : key === 'ruz'
      ? renderRuz(displayValue)
      : key === 'crz' ? renderCrz(displayValue) : renderValue(displayValue);

  return `
    <section class="panel ${active ? 'active' : ''}" id="panel-${key}" role="tabpanel">
      <h2 class="panel-title">${formatKey(key)}</h2>
      ${body}
      ${attribution}
    </section>
  `;
}

function activateTab(key) {
  document.querySelectorAll('.tab-button').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === key);
    tab.setAttribute('aria-selected', tab.dataset.tab === key ? 'true' : 'false');
  });
  document.querySelectorAll('.panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `panel-${key}`);
  });
}

function renderResults(data) {
  latestData = data;
  latestRawJson = JSON.stringify(data, null, 2);
  const includeGeneralInfo = sourceInputs.every(input => input.checked);
  const preferredOrder = [
    ...(includeGeneralInfo ? ['ico'] : []),
    'orsr',
    'rpvs',
    'finstat',
    'ruz',
    'crz'
  ];
  const keys = preferredOrder.filter(key => key in data);
  Object.keys(data).forEach(key => {
    if (key === 'ico' && !includeGeneralInfo) return;
    if (!keys.includes(key)) keys.push(key);
  });
  keys.push('raw');

  tabs.className = 'tabs visible';
  tabs.innerHTML = keys.map((key, index) => `
    <button class="tab-button ${index === 0 ? 'active' : ''}" type="button" data-tab="${key}" aria-controls="panel-${key}" aria-selected="${index === 0 ? 'true' : 'false'}">
      ${formatKey(key)}
    </button>
  `).join('');

  results.innerHTML = keys.map((key, index) => {
    const value = key === 'raw' || key === 'ico' ? data : data[key];
    return renderPanel(key, value, index === 0);
  }).join('');

  tabs.querySelectorAll('.tab-button').forEach(tab => {
    tab.addEventListener('click', () => activateTab(tab.dataset.tab));
  });
  bindExportButtons();
  bindRuzTables();
}

sourceInputs.forEach(sourceInput => {
  sourceInput.addEventListener('change', syncCrzOptionsVisibility);
});
syncCrzOptionsVisibility();

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const ico = input.value.trim();
  const sources = selectedSources();
  if (sources.length === 0) {
    statusEl.className = 'status error';
    statusEl.textContent = 'Vyberte aspoň jeden zdroj informácií.';
    clearResults();
    return;
  }
  statusEl.className = 'status';
  statusEl.textContent = 'Spracúvam požiadavku...';
  button.disabled = true;
  clearResults('Čakám na výsledok zo zdrojov...');

  try {
    const params = new URLSearchParams({ ico, sources: sources.join(',') });
    if (sources.includes('crz') && !crzKeepLegalFormInput.checked) {
      params.set('crz_omit_legal_form', '1');
    }
    const response = await fetch(`/scrape?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Požiadavka zlyhala.');
    }
    renderResults(data);
    statusEl.textContent = 'Hotovo.';
  } catch (error) {
    statusEl.className = 'status error';
    statusEl.textContent = error.message;
    clearResults('Výsledok sa nepodarilo načítať.');
  } finally {
    button.disabled = false;
  }
});
