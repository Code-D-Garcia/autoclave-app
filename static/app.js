

document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentResponseData = null;
    let selectedLotId = null;
    let readingsCount = 0;

    // DOM Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const jsonEditor = document.getElementById('json-editor');
    const btnFormatJson = document.getElementById('btn-format-json');
    const btnSubmitJson = document.getElementById('btn-submit-json');
    const btnLoadSample = document.getElementById('btn-load-sample');
    const btnExportJson = document.getElementById('btn-export-json');
    const btnClearAll = document.getElementById('btn-clear-all');

    const statTotal = document.getElementById('stat-total');
    const statApproved = document.getElementById('stat-approved');
    const statOnHold = document.getElementById('stat-onhold');
    const statRejected = document.getElementById('stat-rejected');
    const statTotalFoot = document.getElementById('stat-total-foot');

    const searchInput = document.getElementById('lot-search-input');
    const filterSelect = document.getElementById('lot-filter-status');
    const lotsListContainer = document.getElementById('lots-list-container');

    const detailEmptyView = document.getElementById('detail-empty-view');
    const detailContentView = document.getElementById('detail-content-view');

    // Tab Navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        });
    });

    // File Upload Setup
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (!file.name.endsWith('.json')) {
            showToast('El archivo debe tener extensión .json');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);

        try {
            showToast('Procesando archivo...');
            const res = await fetch('/api/process-file', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (!res.ok) {
                if (!checkAndDisplayErrors(data)) {
                    showErrorModal('⚠️ Error al Procesar Archivo', data.detail || 'Error procesando archivo');
                }
                return;
            }
            checkAndDisplayErrors(data);
            renderResults(data);
            showToast(`Archivo '${file.name}' procesado con éxito.`);
        } catch (err) {
            showToast(`Error: ${err.message}`, 6000);
        }
    }

    // JSON Editor Actions
    btnFormatJson.addEventListener('click', () => {
        try {
            const raw = jsonEditor.value.trim();
            if (!raw) return;
            const parsed = JSON.parse(raw);
            jsonEditor.value = JSON.stringify(parsed, null, 2);
        } catch (e) {
            showToast('JSON inválido. No se pudo formatear.');
        }
    });

    btnSubmitJson.addEventListener('click', async () => {
        const raw = jsonEditor.value.trim();
        if (!raw) {
            showToast('Por favor ingrese un JSON en el editor.');
            return;
        }
        try {
            const payload = JSON.parse(raw);
            showToast('Enviando JSON al servidor...');
            const res = await fetch('/api/process-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) {
                if (!checkAndDisplayErrors(data)) {
                    showErrorModal('⚠️ Error en JSON', data.detail || 'Error al procesar JSON');
                }
                return;
            }
            checkAndDisplayErrors(data);
            renderResults(data);
            showToast('JSON procesado correctamente.');
        } catch (err) {
            showToast(`Error: ${err.message}`, 6000);
        }
    });

    // Sample Data Loader
    btnLoadSample.addEventListener('click', async () => {
        try {
            showToast('Cargando conjunto de datos de muestra...');
            const sampleRes = await fetch('/api/sample-data');
            const sampleData = await sampleRes.json();

            const res = await fetch('/api/process-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(sampleData)
            });
            const data = await res.json();
            if (!res.ok) {
                if (!checkAndDisplayErrors(data)) {
                    showErrorModal('⚠️ Error en Datos de Muestra', data.detail || 'Error en muestra');
                }
                return;
            }
            checkAndDisplayErrors(data);
            jsonEditor.value = JSON.stringify(sampleData, null, 2);
            renderResults(data);
            showToast('¡Lotes de muestra cargados y analizados!');
        } catch (err) {
            showToast(`Error: ${err.message}`);
        }
    });

    // Manual Form Readings Row Adder
    const readingsContainer = document.getElementById('readings-container');
    const btnAddReading = document.getElementById('btn-add-reading-row');

    function adjustIsoStringMinutes(isoStr, minuteOffset) {
        const regex = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2}):(\d{2})(.*)$/;
        const match = isoStr.trim().match(regex);
        if (!match) return isoStr;
        const [_, datePart, hh, mm, ss, tzPart] = match;
        let d = new Date(`${datePart}T${hh}:${mm}:${ss}`);
        if (isNaN(d.getTime())) return isoStr;
        d.setMinutes(d.getMinutes() + minuteOffset);
        const pad = (n) => String(n).padStart(2, '0');
        const yyyy = d.getFullYear();
        const mo = pad(d.getMonth() + 1);
        const dd = pad(d.getDate());
        const h = pad(d.getHours());
        const m = pad(d.getMinutes());
        const s = pad(d.getSeconds());
        const tz = tzPart || '-05:00';
        return `${yyyy}-${mo}-${dd}T${h}:${m}:${s}${tz}`;
    }

    function updateStartEndTimes() {
        const timeInputs = Array.from(readingsContainer.querySelectorAll('.r-time'))
            .map(input => input.value.trim())
            .filter(v => v.length > 0);

        if (timeInputs.length === 0) return;

        timeInputs.sort();
        const firstTime = timeInputs[0];
        const lastTime = timeInputs[timeInputs.length - 1];

        document.getElementById('m-start').value = adjustIsoStringMinutes(firstTime, -10);
        document.getElementById('m-end').value = adjustIsoStringMinutes(lastTime, +10);
    }

    function addReadingRow(timeIso = '', temp = 118.0, press = 1.35) {
        readingsCount++;
        const row = document.createElement('div');
        row.className = 'reading-input-row';
        row.dataset.rowId = readingsCount;
        row.innerHTML = `
            <input type="text" class="r-time" placeholder="2026-08-01T10:15:00-05:00" value="${timeIso}">
            <input type="number" step="0.1" class="r-temp" placeholder="°C" value="${temp}">
            <input type="number" step="0.1" class="r-press" placeholder="bar" value="${press}">
            <button type="button" class="btn-remove-row" title="Eliminar lectura">&times;</button>
        `;
        row.querySelector('.btn-remove-row').addEventListener('click', () => {
            row.remove();
            updateStartEndTimes();
        });
        row.querySelector('.r-time').addEventListener('input', updateStartEndTimes);
        readingsContainer.appendChild(row);
        updateStartEndTimes();
    }

    addReadingRow('2026-08-01T10:15:00-05:00', 118.0, 1.30);
    addReadingRow('2026-08-01T10:30:00-05:00', 120.5, 1.45);
    addReadingRow('2026-08-01T10:45:00-05:00', 119.0, 1.50);

    btnAddReading.addEventListener('click', () => {
        const nowIso = new Date().toISOString().substring(0, 19) + '-05:00';
        addReadingRow(nowIso, 120.0, 1.4);
    });

    // Manual Form Submit
    const manualForm = document.getElementById('manual-lot-form');
    manualForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        updateStartEndTimes();

        const lotId = document.getElementById('m-lot-id').value.trim();
        const product = document.getElementById('m-product').value.trim();
        const autoclave = document.getElementById('m-autoclave').value.trim();
        const startTime = document.getElementById('m-start').value.trim();
        const endTime = document.getElementById('m-end').value.trim();
        const minTemp = parseFloat(document.getElementById('m-min-temp').value);
        const maxTemp = parseFloat(document.getElementById('m-max-temp').value);
        const minPress = parseFloat(document.getElementById('m-min-press').value);
        const maxPress = parseFloat(document.getElementById('m-max-press').value);

        const readingRows = readingsContainer.querySelectorAll('.reading-input-row');
        const readings = [];
        readingRows.forEach(r => {
            const time = r.querySelector('.r-time').value.trim();
            const t = parseFloat(r.querySelector('.r-temp').value);
            const p = parseFloat(r.querySelector('.r-press').value);
            if (time && !isNaN(t) && !isNaN(p)) {
                readings.push({ timestamp: time, temperature: t, pressure: p });
            }
        });

        const lotPayload = {
            lot_id: lotId,
            product,
            autoclave,
            start_time: startTime,
            end_time: endTime,
            min_temperature: minTemp,
            max_temperature: maxTemp,
            min_pressure: minPress,
            max_pressure: maxPress,
            readings
        };

        try {
            showToast('Procesando lote manual...');
            const res = await fetch('/api/process-lot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lotPayload)
            });
            const lotReport = await res.json();
            if (!res.ok) {
                if (!checkAndDisplayErrors(lotReport)) {
                    showErrorModal('⚠️ Error al Crear Lote', lotReport.detail || 'Error validando lote');
                }
                return;
            }

            if (!currentResponseData) {
                currentResponseData = {
                    total_processed_lots: 1,
                    total_failed_lots: 0,
                    Lots: [lotReport]
                };
            } else {
                currentResponseData.Lots.push(lotReport);
                currentResponseData.total_processed_lots = currentResponseData.Lots.length;
            }
            renderResults(currentResponseData);
            selectLot(lotReport.lot_id);
            showToast(`Lote ${lotId} agregado y procesado.`);
        } catch (err) {
            showToast(`Error: ${err.message}`, 6000);
        }
    });

    // Auto-load stored lots from DB/memory on startup (Page reload persistence)
    async function loadInitialStoredLots() {
        try {
            const res = await fetch('/api/lots');
            const data = await res.json();
            if (data.Lots && data.Lots.length > 0) {
                renderResults(data);
                showToast(`Historial cargado desde BD (${data.Lots.length} lotes).`);
            }
        } catch (e) {
            console.log('Sin historial inicial:', e);
        }
    }
    loadInitialStoredLots();

    // Clear All (Removes from DB and UI)
    btnClearAll.addEventListener('click', async () => {
        try {
            showToast('Limpiando base de datos e historial...');
            await fetch('/api/lots', { method: 'DELETE' });
        } catch (e) {
            console.error('Error al limpiar BD:', e);
        }

        currentResponseData = null;
        selectedLotId = null;
        lotsListContainer.innerHTML = `
            <div class="empty-state">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <p>No hay lotes cargados en este momento.</p>
                <span class="subtext">Sube un archivo JSON o usa "Cargar Datos de Muestra".</span>
            </div>
        `;
        statTotal.textContent = '0';
        statApproved.textContent = '0';
        statOnHold.textContent = '0';
        statRejected.textContent = '0';
        statTotalFoot.textContent = 'Esperando datos';
        detailContentView.classList.add('hidden');
        detailEmptyView.classList.remove('hidden');
        btnExportJson.disabled = true;
        showToast('Base de datos y vista limpiadas.');
    });

    // Export JSON
    btnExportJson.addEventListener('click', () => {
        if (!currentResponseData) return;
        const blob = new Blob([JSON.stringify(currentResponseData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reporte_autoclave_${new Date().toISOString().slice(0,10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
    });

    // Filters and Search
    searchInput.addEventListener('input', filterAndRenderLots);
    filterSelect.addEventListener('change', filterAndRenderLots);

    function filterAndRenderLots() {
        if (!currentResponseData) return;
        const query = searchInput.value.toLowerCase().trim();
        const statusFilter = filterSelect.value;

        const validLots = (currentResponseData.Lots || []).filter(lot => {
            const matchesQuery = lot.lot_id.toLowerCase().includes(query) ||
                                 lot.product.toLowerCase().includes(query) ||
                                 lot.autoclave.toLowerCase().includes(query);
            const matchesStatus = (statusFilter === 'ALL') || (lot.status === statusFilter);
            return matchesQuery && matchesStatus;
        });

        const failedLots = (currentResponseData.errors || []).filter(err => {
            const matchesQuery = err.lot_id.toLowerCase().includes(query) ||
                                 err.error.toLowerCase().includes(query);
            const matchesStatus = (statusFilter === 'ALL' || statusFilter === 'ERRORS' || statusFilter === 'REJECTED');
            return matchesQuery && matchesStatus;
        });

        renderLotCards(validLots, failedLots);
    }

    // Render Full Results (Con preservación de lotes y filtrado de duplicados)
    function renderResults(data) {
        if (!data) return;

        // Si ya existen datos previos en la vista, fusionar sin perder lo procesado
        if (!currentResponseData) {
            currentResponseData = {
                total_processed_lots: 0,
                total_failed_lots: 0,
                Lots: [],
                errors: []
            };
        }

        const existingLotsMap = new Map();
        (currentResponseData.Lots || []).forEach(l => existingLotsMap.set(l.lot_id, l));

        // Agregar/Actualizar nuevos lotes procesados exitosamente
        (data.Lots || []).forEach(l => existingLotsMap.set(l.lot_id, l));
        currentResponseData.Lots = Array.from(existingLotsMap.values());

        // Filtrar errores: No mostrar como tarjetas de error los duplicados (ya mostrados en Modal)
        // ni sobreescribir lotes que ya fueron procesados con éxito
        const filteredNewErrors = (data.errors || []).filter(err => {
            const isDuplicate = err.error && err.error.toLowerCase().includes('duplicado');
            const isAlreadyLoaded = (err.lot_id && existingLotsMap.has(err.lot_id)) || 
                                    (err.error && Array.from(existingLotsMap.keys()).some(k => err.error.includes(k)));
            return !isDuplicate && !isAlreadyLoaded;
        });

        currentResponseData.errors = filteredNewErrors;
        currentResponseData.total_processed_lots = currentResponseData.Lots.length;
        currentResponseData.total_failed_lots = currentResponseData.errors.length;

        btnExportJson.disabled = false;

        const lots = currentResponseData.Lots || [];
        const errors = currentResponseData.errors || [];

        let approved = 0;
        let onHold = 0;
        let rejected = 0;

        lots.forEach(l => {
            if (l.status === 'APPROVED') approved++;
            else if (l.status === 'ON_HOLD') onHold++;
            else if (l.status === 'REJECTED') rejected++;
        });

        statTotal.textContent = lots.length + errors.length;
        statApproved.textContent = approved;
        statOnHold.textContent = onHold;
        statRejected.textContent = rejected + errors.length;
        statTotalFoot.textContent = errors.length > 0 ? `⚠️ ${errors.length} con error de formato` : '0 Errores de estructura';

        filterAndRenderLots();

        if (!selectedLotId && lots.length > 0) {
            selectLot(lots[0].lot_id);
        } else if (selectedLotId && existingLotsMap.has(selectedLotId)) {
            selectLot(selectedLotId);
        } else if (errors.length > 0) {
            selectFailedLot(errors[0]);
        }
    }

    function renderLotCards(lots, errors) {
        lotsListContainer.innerHTML = '';
        if (lots.length === 0 && errors.length === 0) {
            lotsListContainer.innerHTML = `<div class="empty-state"><p>No se encontraron lotes con los filtros seleccionados.</p></div>`;
            return;
        }

        // Render valid lots
        lots.forEach(lot => {
            const card = document.createElement('div');
            card.className = `lot-item-card ${lot.lot_id === selectedLotId ? 'active' : ''}`;
            card.dataset.lotId = lot.lot_id;
            
            const badgeClass = `badge-${lot.status}`;
            const alertBadge = lot.summary.alert_count > 0 ? `<span style="color:#f87171; font-weight:bold;">🚨 ${lot.summary.alert_count} Alertas</span>` : `<span style="color:#34d399;">✓ OK</span>`;

            card.innerHTML = `
                <div class="lot-item-header">
                    <span class="lot-item-id">${lot.lot_id}</span>
                    <span class="badge ${badgeClass}">${lot.status}</span>
                </div>
                <div class="lot-item-product">${lot.product}</div>
                <div class="lot-item-meta">
                    <span>${lot.autoclave}</span>
                    <span>${alertBadge}</span>
                </div>
            `;

            card.addEventListener('click', () => selectLot(lot.lot_id));
            lotsListContainer.appendChild(card);
        });

        // Render failed lots with clear warning badge
        errors.forEach(err => {
            const card = document.createElement('div');
            card.className = `lot-item-card ${err.lot_id === selectedLotId ? 'active' : ''}`;
            card.style.borderLeft = '3px solid #ef4444';
            card.dataset.lotId = err.lot_id;

            card.innerHTML = `
                <div class="lot-item-header">
                    <span class="lot-item-id">${err.lot_id}</span>
                    <span class="badge badge-REJECTED">ERROR FORMATO</span>
                </div>
                <div class="lot-item-product" style="color:#f87171;">${err.error}</div>
                <div class="lot-item-meta">
                    <span>Sin telemetría</span>
                    <span>❌ Reclamar JSON</span>
                </div>
            `;

            card.addEventListener('click', () => selectFailedLot(err));
            lotsListContainer.appendChild(card);
        });
    }

    function selectLot(lotId) {
        if (!currentResponseData || !currentResponseData.Lots) return;
        const lot = currentResponseData.Lots.find(l => l.lot_id === lotId);
        if (!lot) return;

        selectedLotId = lotId;

        document.querySelectorAll('.lot-item-card').forEach(c => {
            c.classList.toggle('active', c.dataset.lotId === lotId);
        });

        detailEmptyView.classList.add('hidden');
        detailContentView.classList.remove('hidden');

        document.getElementById('det-lot-id').textContent = lot.lot_id;
        document.getElementById('det-product').textContent = lot.product;
        document.getElementById('det-autoclave').textContent = lot.autoclave;
        
        const badgeElem = document.getElementById('det-status-badge');
        badgeElem.textContent = lot.status;
        badgeElem.className = `badge badge-${lot.status}`;

        const startDt = new Date(lot.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const endDt = new Date(lot.end_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        document.getElementById('det-time-range').textContent = `${startDt} - ${endDt}`;
        
        document.getElementById('det-temp-range').textContent = `Min ${lot.summary.min_temperature_registered}°C / Max ${lot.summary.max_temperature_registered}°C`;
        document.getElementById('det-press-range').textContent = `Min ${lot.summary.min_pressure_registered} / Max ${lot.summary.max_pressure_registered} bar`;
        document.getElementById('det-averages').textContent = `${lot.summary.avg_temperature}°C | ${lot.summary.avg_pressure} bar`;

        const alertsCard = document.getElementById('alerts-card');
        const alertsTableBody = document.querySelector('#alerts-table tbody');
        alertsTableBody.innerHTML = '';

        if (lot.alerts && lot.alerts.length > 0) {
            alertsCard.classList.remove('hidden');
            document.getElementById('alert-count-num').textContent = lot.alerts.length;
            lot.alerts.forEach(a => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${new Date(a.date).toLocaleTimeString()}</td>
                    <td><strong>${a.temperature}°C</strong></td>
                    <td><strong>${a.pressure} bar</strong></td>
                    <td><span class="badge badge-REJECTED">${a.classification}</span></td>
                `;
                alertsTableBody.appendChild(tr);
            });
        } else {
            alertsCard.classList.add('hidden');
        }

        // Populate readings table directly
        const readings = lot.readings || [];
        const readingsTableBody = document.querySelector('#readings-table tbody');
        readingsTableBody.innerHTML = '';
        document.getElementById('readings-count-num').textContent = readings.length;

        readings.forEach((r, idx) => {
            const tr = document.createElement('tr');
            const statusTag = (r.classification && r.classification !== 'NORMAL') ? 
                `<span class="badge badge-ON_HOLD">${r.classification}</span>` : 
                `<span class="badge badge-APPROVED">NORMAL</span>`;

            tr.innerHTML = `
                <td>${idx + 1}</td>
                <td>${new Date(r.timestamp).toLocaleTimeString()}</td>
                <td>${r.temperature}°C</td>
                <td>${r.pressure} bar</td>
                <td>${statusTag}</td>
            `;
            readingsTableBody.appendChild(tr);
        });
    }

    function selectFailedLot(err) {
        selectedLotId = err.lot_id;
        document.querySelectorAll('.lot-item-card').forEach(c => {
            c.classList.toggle('active', c.dataset.lotId === err.lot_id);
        });

        detailEmptyView.classList.add('hidden');
        detailContentView.classList.remove('hidden');

        document.getElementById('det-lot-id').textContent = err.lot_id;
        document.getElementById('det-product').textContent = 'Error de estructura en JSON';
        document.getElementById('det-autoclave').textContent = 'N/A';

        const badgeElem = document.getElementById('det-status-badge');
        badgeElem.textContent = 'INVALID_JSON';
        badgeElem.className = 'badge badge-REJECTED';

        document.getElementById('det-time-range').textContent = 'N/A';
        document.getElementById('det-temp-range').textContent = 'N/A';
        document.getElementById('det-press-range').textContent = 'N/A';
        document.getElementById('det-averages').textContent = 'N/A';

        const alertsCard = document.getElementById('alerts-card');
        alertsCard.classList.remove('hidden');
        document.getElementById('alert-count-num').textContent = 1;
        const alertsTableBody = document.querySelector('#alerts-table tbody');
        alertsTableBody.innerHTML = `
            <tr>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td><span class="badge badge-REJECTED">${err.error}</span></td>
            </tr>
        `;

        document.querySelector('#readings-table tbody').innerHTML = `
            <tr><td colspan="5" style="color:#f87171;">Imposible procesar lecturas debido al error de validación en el lote.</td></tr>
        `;
    }

    // PostgreSQL Analytics Modal Handling
    const btnShowAnalytics = document.getElementById('btn-show-analytics');
    const btnCloseAnalytics = document.getElementById('btn-close-analytics');
    const analyticsModal = document.getElementById('analytics-modal');

    if (btnShowAnalytics && analyticsModal) {
        btnShowAnalytics.addEventListener('click', async () => {
            try {
                showToast('Consultando métricas en PostgreSQL...');
                const res = await fetch('/api/analytics');
                const data = await res.json();
                
                const metrics = data.metrics || [];
                const tbody = document.querySelector('#db-analytics-table tbody');
                tbody.innerHTML = '';

                let totalLotes = 0;
                let totalAlertas = 0;
                const autoclavesSet = new Set();

                if (metrics.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#94a3b8;">No se encontraron datos analíticos guardados en PostgreSQL aún.</td></tr>`;
                } else {
                    metrics.forEach(m => {
                        totalLotes += m.lotes_procesados || 0;
                        totalAlertas += m.total_lecturas_fuera_de_rango || 0;
                        autoclavesSet.add(m.autoclave_id);

                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><strong>${m.autoclave_id}</strong></td>
                            <td>${m.mes}</td>
                            <td>${m.lotes_procesados}</td>
                            <td>${m.temperatura_promedio}°C</td>
                            <td>${m.total_lecturas_fuera_de_rango > 0 ? `<span style="color:#f87171; font-weight:bold;">${m.total_lecturas_fuera_de_rango}</span>` : '0'}</td>
                            <td><span class="badge ${m.porcentaje_lotes_aprobados === 100 ? 'badge-APPROVED' : 'badge-ON_HOLD'}">${m.porcentaje_lotes_aprobados}%</span></td>
                        `;
                        tbody.appendChild(tr);
                    });
                }

                document.getElementById('db-stat-autoclaves').textContent = autoclavesSet.size;
                document.getElementById('db-stat-lotes').textContent = totalLotes;
                document.getElementById('db-stat-alertas').textContent = totalAlertas;

                analyticsModal.classList.remove('hidden');
            } catch (err) {
                showToast(`Error al consultar BD: ${err.message}`, 6000);
            }
        });

        if (btnCloseAnalytics) {
            btnCloseAnalytics.addEventListener('click', () => {
                analyticsModal.classList.add('hidden');
            });
        }

        analyticsModal.addEventListener('click', (e) => {
            if (e.target === analyticsModal) {
                analyticsModal.classList.add('hidden');
            }
        });
    }

    // Error Modal Handler for Duplicates and Validations
    const errorModal = document.getElementById('error-modal');
    const btnCloseError = document.getElementById('btn-close-error');
    const btnErrorAccept = document.getElementById('btn-error-accept');

    function showErrorModal(title, msg) {
        if (!errorModal) return;
        document.getElementById('error-modal-title').textContent = title || '⚠️ Lote Duplicado Detectado';
        document.getElementById('error-modal-message').textContent = msg || 'Ocurrió un error de validación en el lote.';
        errorModal.classList.remove('hidden');
    }

    function checkAndDisplayErrors(data) {
        if (!data) return false;
        if (data.errors && data.errors.length > 0) {
            const dupErr = data.errors.find(e => e.error && e.error.toLowerCase().includes('duplicado'));
            if (dupErr) {
                showErrorModal('⚠️ Lote Duplicado Detectado', dupErr.error);
                return true;
            }
            showErrorModal('⚠️ Error de Validación', data.errors[0].error);
            return true;
        }
        if (data.detail && typeof data.detail === 'string' && data.detail.toLowerCase().includes('duplicado')) {
            showErrorModal('⚠️ Lote Duplicado Detectado', data.detail);
            return true;
        }
        return false;
    }

    if (btnCloseError) btnCloseError.addEventListener('click', () => errorModal.classList.add('hidden'));
    if (btnErrorAccept) btnErrorAccept.addEventListener('click', () => errorModal.classList.add('hidden'));
    if (errorModal) {
        errorModal.addEventListener('click', (e) => {
            if (e.target === errorModal) errorModal.classList.add('hidden');
        });
    }

    function showToast(msg, duration = 4000) {
        const toast = document.getElementById('toast');
        document.getElementById('toast-message').textContent = msg;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), duration);
    }
});
