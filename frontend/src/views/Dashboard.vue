<template>
  <div class="workspace">
    <section class="map-stage" aria-label="Soil moisture map">
      <div ref="mapElement" class="map-canvas" />
      <img v-if="fallbackImageUrl" ref="productImageElement" :src="fallbackImageUrl" :style="productImageStyle" class="product-fallback-image" alt="Daily soil moisture product" @load="positionPointMarker" @error="errorMessage = 'Unable to load the local PNG product.'" />
      <div v-if="selectedPoint && pointMarkerStyle" class="selected-point-marker" :style="pointMarkerStyle" role="img" aria-label="Selected analysis point"><span /></div>
      <div v-if="pointAnalysisEnabled" class="point-capture-layer" aria-label="Point analysis map click area" @click="handleCaptureClick" />

      <div class="basemap-switch" role="group" aria-label="Basemap selection">
        <span class="switch-label">Basemap</span>
        <button :class="['switch-button', { active: basemapMode === 'satellite' }]" type="button" @click="setBasemap('satellite')">
          <i class="fa-solid fa-satellite" /> Satellite
        </button>
        <button :class="['switch-button', { active: basemapMode === 'standard' }]" type="button" @click="setBasemap('standard')">
          <i class="fa-solid fa-map" /> Standard
        </button>
      </div>

      <div class="map-heading">
        <div class="monitoring-label"><span class="eyebrow">MONITORING AREA</span><button class="project-toggle" type="button" title="Show other projects" aria-label="Show other projects" @click.stop="projectsOpen = !projectsOpen"><i class="fa-solid fa-caret-down" /></button></div>
        <h1>{{ polygonName || 'Jiefangzha' }}</h1>
        <p>Daily product · 100 m · {{ selectedDate || '2018-05-01 to 2018-05-24' }}</p>
        <div v-if="projectsOpen" class="project-menu">
          <div v-if="!projectOptions.length" class="project-empty">No other projects</div>
          <div v-for="project in projectOptions" :key="project.id" class="project-item">
            <button type="button" class="project-name" @click="selectProject(project)">{{ project.name }} · {{ project.start_date }} to {{ project.end_date }}</button>
            <button type="button" class="project-delete" :disabled="project.isDefault" :title="project.isDefault ? 'The default Jiefangzha project cannot be deleted' : 'Delete project'" :aria-label="project.isDefault ? 'The default Jiefangzha project cannot be deleted' : 'Delete project'" @click.stop="deleteProject(project)"><i class="fa-solid fa-trash" /></button>
          </div>
        </div>
      </div>

      <div class="legend" aria-label="Volumetric soil moisture color scale">
        <span class="legend-title">Soil moisture <b>m³/m³</b></span>
        <div class="legend-scale" />
        <div class="legend-labels"><span>0.00</span><span>0.20</span><span>0.40</span></div>
      </div>

      <div v-if="mapMessage" class="map-message">
        <i class="fa-solid fa-circle-info" />
        <span>{{ mapMessage }}</span>
      </div>

      <div v-if="loadingImage" class="map-loading">
        <i class="fa-solid fa-spinner fa-spin" /> Loading daily product
      </div>
    </section>

    <aside class="inspector">
      <div class="section-header">
        <div>
          <span class="eyebrow">PRODUCT INSPECTOR</span>
          <h2>Daily observation</h2>
        </div>
        <span class="quality-badge"><i class="fa-solid fa-circle-check" /> {{ resultStatus }}</span>
      </div>

      <div class="date-control">
        <button class="icon-button" title="Previous day" aria-label="Previous day" :disabled="dateIndex <= 0" @click="stepDate(-1)">
          <i class="fa-solid fa-chevron-left" />
        </button>
        <label>
          <span>Date</span>
          <input v-model="selectedDate" type="date" :min="firstDate" :max="lastDate" @change="selectDate(selectedDate)" />
        </label>
        <button class="icon-button" title="Next day" aria-label="Next day" :disabled="dateIndex >= dates.length - 1" @click="stepDate(1)">
          <i class="fa-solid fa-chevron-right" />
        </button>
        <button class="icon-button" :title="playing ? 'Pause animation' : 'Play animation'" :aria-label="playing ? 'Pause animation' : 'Play animation'" @click="togglePlayback">
          <i :class="playing ? 'fa-solid fa-pause' : 'fa-solid fa-play'" />
        </button>
      </div>

      <div class="location-panel">
        <div class="panel-title">
          <div>
            <span class="eyebrow">POINT ANALYSIS</span>
            <h3>Field time series</h3>
          </div>
          <i class="fa-solid fa-location-crosshairs" />
        </div>
        <button class="analysis-button" :class="{ active: pointAnalysisEnabled }" type="button" @click="togglePointAnalysis">
          <i :class="pointAnalysisEnabled ? 'fa-solid fa-hand-pointer' : 'fa-solid fa-location-crosshairs'" />
          {{ pointAnalysisEnabled ? 'Point analysis enabled · click map to update' : 'Enable point analysis' }}
        </button>
        <div v-if="pointAnalysisEnabled" class="nasa-region-download">
          <div v-if="checkingNasaCoverage && !nasaCoverage" class="nasa-region-status"><i class="fa-solid fa-spinner fa-spin" /> Checking NASA data coverage</div>
          <template v-else-if="nasaCoverage?.status === 'completed'">
            <div class="nasa-region-status complete"><i class="fa-solid fa-circle-check" /> All NASA data downloaded</div>
          </template>
          <template v-else>
            <button class="secondary-button nasa-region-button" :disabled="downloadingNasaRegion || nasaCoverage?.status === 'downloading'" type="button" @click="startNasaRegionDownload">
              <i :class="downloadingNasaRegion || nasaCoverage?.status === 'downloading' ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-cloud-arrow-down'" />
              {{ downloadingNasaRegion || nasaCoverage?.status === 'downloading' ? 'Downloading NASA data' : 'Download NASA data' }}
            </button>
            <small v-if="nasaCoverage">{{ nasaCoverage.downloaded }} / {{ nasaCoverage.total }} NASA POWER grid cells cached</small>
          </template>
        </div>
        <p v-if="!selectedPoint" class="empty-copy">Select a point inside the field boundary to inspect its 24-day time series.</p>
        <template v-else>
          <div class="coordinate-row">
            <span>{{ selectedPoint.lng.toFixed(5) }}° E <small>(GCJ-02)</small></span>
            <span>{{ selectedPoint.lat.toFixed(5) }}° N <small>(GCJ-02)</small></span>
          </div>
          <button class="primary-button" :disabled="loadingSeries" @click="loadTimeSeries">
            <i :class="loadingSeries ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-chart-line'" />
            {{ loadingSeries ? 'Loading point analysis' : 'Reload point analysis' }}
          </button>
        </template>
        <div v-if="weatherData && selectedWeather" class="weather-panel">
          <div class="panel-title weather-title">
            <div>
              <span class="eyebrow">POINT INFORMATION</span>
              <h3>{{ selectedWeather.date }}</h3>
            </div>
            <i class="fa-solid fa-cloud-sun" />
          </div>
          <div class="weather-grid">
            <div><span>Soil moisture</span><strong>{{ selectedWeather.moisture }}</strong><small>m³/m³</small></div>
            <div><span>Temperature</span><strong>{{ selectedWeather.temperature }}</strong><small>°C (min / max)</small></div>
            <div><span>Rainfall</span><strong>{{ selectedWeather.rain }}</strong><small>mm</small></div>
            <div><span>Wind speed</span><strong>{{ selectedWeather.wind }}</strong><small>m/s</small></div>
            <div><span>Dew point</span><strong>{{ selectedWeather.dewPoint }}</strong><small>°C</small></div>
            <div><span>Relative humidity</span><strong>{{ selectedWeather.humidity }}</strong><small>%</small></div>
          </div>
          <p v-if="weatherData.site_info" class="nasa-source">
            NASA POWER: {{ weatherData.site_info.nasa_cached ? 'loaded from local cache' : 'downloaded and cached' }}
          </p>
          <p v-if="weatherData.warning" class="weather-warning">{{ weatherData.warning }}</p>
        </div>
        <div v-show="seriesReady" ref="chartElement" class="series-chart" />
      </div>

      <div v-if="errorMessage" class="error-message"><i class="fa-solid fa-triangle-exclamation" /> {{ errorMessage }}</div>

      <div class="action-row">
        <button class="secondary-button" :disabled="!selectedDate" @click="downloadTif">
          <i class="fa-solid fa-download" /> Download GeoTIFF
        </button>
        <button class="icon-button" title="Fit field boundary" aria-label="Fit field boundary" @click="fitBoundary">
          <i class="fa-solid fa-expand" />
        </button>
      </div>

      <footer class="metadata">
        <span>Dataset ID {{ resultSetId || '—' }}</span>
        <span>{{ dates.length }} daily products</span>
        <span>EPSG:4326</span>
      </footer>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import AMapLoader from '@amap/amap-jsapi-loader';
import api from '../services/axios.js';

const emit = defineEmits(['api-status']);
const route = useRoute();
const mapElement = ref(null);
const chartElement = ref(null);
const polygonName = ref('');
const polygonId = ref(83);
const projectsOpen = ref(false);
const projectOptions = ref([]);
const dates = ref([]);
const selectedDate = ref('');
const selectedPoint = ref(null);
const resultSetId = ref(null);
const resultStatus = ref('READY');
const mapMessage = ref('');
const fallbackImageUrl = ref('');
const productImageStyle = ref({});
const productImageElement = ref(null);
const pointMarkerStyle = ref(null);
let productBounds = null;
let imageRequest = 0;
let disposed = false;
const errorMessage = ref('');
const loadingImage = ref(false);
const loadingSeries = ref(false);
const checkingNasaCoverage = ref(false);
const downloadingNasaRegion = ref(false);
const nasaCoverage = ref(null);
const seriesReady = ref(false);
const weatherData = ref(null);
const playing = ref(false);
const basemapMode = ref('satellite');
const pointAnalysisEnabled = ref(false);

let AMap = null;
let map = null;
let boundaryOverlay = null;
let chart = null;
let playbackTimer = null;
let polygonCoordinates = [];
let satelliteLayer = null;
let standardLayer = null;
let nasaCoverageTimer = null;
let imageObjectUrl = null;

const dateIndex = computed(() => dates.value.indexOf(selectedDate.value));
const firstDate = computed(() => dates.value.at(0) || '');
const lastDate = computed(() => dates.value.at(-1) || '');
const selectedWeather = computed(() => {
  if (!weatherData.value?.dates?.length || !selectedDate.value) return null;
  const index = weatherData.value.dates.indexOf(selectedDate.value);
  if (index < 0) return null;
  const temperature = weatherData.value.series?.temperature || {};
  const value = (items, fallback = null) => {
    const item = items?.[index];
    if (item === null || item === undefined || item === '') return fallback;
    return Number.isFinite(Number(item)) ? Number(item) : fallback;
  };
  const min = value(temperature.tmin);
  const max = value(temperature.tmax);
  const moisture = value(weatherData.value.series?.moisture, null);
  return {
    date: selectedDate.value,
    moisture: moisture === null ? '—' : moisture.toFixed(2),
    temperature: min === null || max === null ? '—' : `${min.toFixed(1)} / ${max.toFixed(1)}`,
    rain: value(weatherData.value.series?.rain, null) === null ? '—' : value(weatherData.value.series.rain).toFixed(2),
    wind: value(weatherData.value.series?.wind, null) === null ? '—' : value(weatherData.value.series.wind).toFixed(1),
    dewPoint: value(weatherData.value.series?.dew_point, null) === null ? '—' : value(weatherData.value.series.dew_point).toFixed(1),
    humidity: value(weatherData.value.series?.humidity, null) === null ? '—' : value(weatherData.value.series.humidity).toFixed(1),
  };
});

async function initializeMap() {
  const key = import.meta.env.VITE_AMAP_KEY;
  if (!key) {
    mapMessage.value = 'Basemap unavailable';
    return;
  }
  if (import.meta.env.VITE_AMAP_SECURITY_CODE) {
    window._AMapSecurityConfig = { securityJsCode: import.meta.env.VITE_AMAP_SECURITY_CODE };
  }
  try {
    let timeout;
    try {
      AMap = await Promise.race([
        AMapLoader.load({ key, version: '2.0', plugins: ['AMap.Scale', 'AMap.ToolBar'] }),
        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('Basemap connection timed out')), 8000); }),
      ]);
    } finally { clearTimeout(timeout); }
    if (disposed) return;
    satelliteLayer = new AMap.TileLayer.Satellite();
    standardLayer = new AMap.TileLayer();
    standardLayer.setOpacity(0);
    map = new AMap.Map(mapElement.value, {
      viewMode: '2D',
      zoom: 8,
      center: [107.04, 40.86],
      layers: [satelliteLayer, standardLayer],
    });
    map.addControl(new AMap.Scale({ position: 'LB' }));
    map.addControl(new AMap.ToolBar({ position: { right: '18px', bottom: '94px' } }));
    map.on('click', handleMapClick);
    for (const event of ['mapmove', 'zoomchange', 'resize', 'complete']) map.on(event, positionProductImage);
    drawBoundary();
    positionProductImage();
  } catch (error) {
    mapMessage.value = `Basemap initialization failed: ${error.message}`;
  }
}

function positionProductImage() {
  positionPointMarker();
  productImageStyle.value = {};
  if (!map || !AMap || !productBounds) return;
  try {
    const sw = productBounds.southwest;
    const ne = productBounds.northeast;
    const topLeft = map.lngLatToContainer(new AMap.LngLat(sw[0], ne[1]));
    const bottomRight = map.lngLatToContainer(new AMap.LngLat(ne[0], sw[1]));
    const width = bottomRight.x - topLeft.x;
    const height = bottomRight.y - topLeft.y;
    if (![topLeft.x, topLeft.y, width, height].every(Number.isFinite) || width <= 0 || height <= 0) return;
    productImageStyle.value = { inset: 'auto', left: `${topLeft.x}px`, top: `${topLeft.y}px`, width: `${width}px`, height: `${height}px`, objectFit: 'fill' };
  } catch { /* Keep the local fitted PNG while the map projection initializes. */ }
}

function positionPointMarker() {
  pointMarkerStyle.value = null;
  if (!selectedPoint.value) return;
  const { lng, lat } = selectedPoint.value;
  let pixel;
  if (map && AMap) {
    pixel = map.lngLatToContainer(new AMap.LngLat(lng, lat));
  } else {
    const rect = fittedProductRect();
    if (!rect || !productBounds) return;
    const { southwest: sw, northeast: ne } = productBounds;
    pixel = { x: rect.left + (lng - sw[0]) / (ne[0] - sw[0]) * rect.width,
      y: rect.top + (ne[1] - lat) / (ne[1] - sw[1]) * rect.height };
  }
  if (Number.isFinite(pixel.x) && Number.isFinite(pixel.y)) {
    pointMarkerStyle.value = { left: `${pixel.x}px`, top: `${pixel.y}px` };
  }
}

function fittedProductRect() {
  const img = productImageElement.value;
  if (!img?.complete || !img.naturalWidth || !mapElement.value) return null;
  const box = img.getBoundingClientRect();
  const stage = mapElement.value.getBoundingClientRect();
  const scale = Math.min(box.width / img.naturalWidth, box.height / img.naturalHeight);
  const width = img.naturalWidth * scale;
  const height = img.naturalHeight * scale;
  return { left: box.left - stage.left + (box.width - width) / 2,
    top: box.top - stage.top + (box.height - height) / 2, width, height };
}

function pointInBoundary({ lng, lat }) {
  if (boundaryOverlay) return boundaryOverlay.contains(new AMap.LngLat(lng, lat));
  let inside = false;
  for (let i = 0, j = polygonCoordinates.length - 1; i < polygonCoordinates.length; j = i++) {
    const [xi, yi] = polygonCoordinates[i];
    const [xj, yj] = polygonCoordinates[j];
    if ((yi > lat) !== (yj > lat) && lng < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function setBasemap(mode) {
  basemapMode.value = mode;
  if (!map || !AMap || !satelliteLayer || !standardLayer) return;
  satelliteLayer.setOpacity(mode === 'satellite' ? 1 : 0);
  standardLayer.setOpacity(mode === 'standard' ? 1 : 0);
  // Do not call map.setLayers here: that replaces the complete layer stack
  // and removes the active PNG ImageLayer and overlays. Both basemap layers
  // are already attached when the map is created, so changing opacity is
  // sufficient and preserves the product image.
}

function drawBoundary() {
  if (!map || !AMap || !polygonCoordinates.length) return;
  if (boundaryOverlay) map.remove(boundaryOverlay);
  boundaryOverlay = new AMap.Polygon({
    path: polygonCoordinates,
    strokeColor: '#47534d',
    strokeWeight: 1,
    strokeOpacity: 0.72,
    fillColor: '#ffffff',
    fillOpacity: 0.02,
    zIndex: 20,
    clickable: false,
  });
  map.add(boundaryOverlay);
  fitBoundary();
}

function fitBoundary() {
  if (map && boundaryOverlay) map.setFitView([boundaryOverlay], false, [56, 56, 56, 56], 10);
}

function togglePointAnalysis() {
  pointAnalysisEnabled.value = !pointAnalysisEnabled.value;
  if (pointAnalysisEnabled.value) {
    errorMessage.value = '';
    void refreshNasaCoverage();
  } else {
    stopNasaCoveragePolling();
  }
}

function stopNasaCoveragePolling() {
  if (nasaCoverageTimer) window.clearInterval(nasaCoverageTimer);
  nasaCoverageTimer = null;
}

function startNasaCoveragePolling() {
  stopNasaCoveragePolling();
  nasaCoverageTimer = window.setInterval(refreshNasaCoverage, 2000);
}

async function refreshNasaCoverage() {
  if (!pointAnalysisEnabled.value || !resultSetId.value) return;
  checkingNasaCoverage.value = true;
  try {
    const response = await api.get('/api/weather_data/region-status/', {
      params: { result_set_id: resultSetId.value },
      timeout: 30000,
    });
    nasaCoverage.value = response.data;
    if (response.data.status === 'downloading') startNasaCoveragePolling();
    else stopNasaCoveragePolling();
  } catch (error) {
    nasaCoverage.value = { status: 'failed', downloaded: 0, total: 0 };
    errorMessage.value = error.response?.data?.message || 'Unable to check NASA POWER data coverage.';
    stopNasaCoveragePolling();
  } finally {
    checkingNasaCoverage.value = false;
  }
}

async function startNasaRegionDownload() {
  if (!resultSetId.value || downloadingNasaRegion.value) return;
  downloadingNasaRegion.value = true;
  errorMessage.value = '';
  try {
    const response = await api.post('/api/weather_data/region-download/', null, {
      params: { result_set_id: resultSetId.value },
      timeout: 30000,
    });
    nasaCoverage.value = response.data;
    startNasaCoveragePolling();
  } catch (error) {
    errorMessage.value = error.response?.data?.message || 'Unable to start NASA POWER data download.';
  } finally {
    downloadingNasaRegion.value = false;
  }
}

function selectPoint(lnglat) {
  if (!pointAnalysisEnabled.value) return;
  if (!pointInBoundary(lnglat)) {
    errorMessage.value = 'Select a point inside the field boundary.';
    return;
  }
  errorMessage.value = '';
  selectedPoint.value = { lng: lnglat.lng, lat: lnglat.lat };
  seriesReady.value = false;
  weatherData.value = null;
  positionPointMarker();
  void loadTimeSeries();
}

function handleMapClick(event) {
  selectPoint(event.lnglat);
}

function handleCaptureClick(event) {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  if (map && AMap) {
    const lnglat = map.containerToLngLat(new AMap.Pixel(x, y));
    if (lnglat) selectPoint(lnglat);
  } else {
    const image = fittedProductRect();
    if (!image || !productBounds || x < image.left || y < image.top
      || x > image.left + image.width || y > image.top + image.height) return;
    const { southwest: sw, northeast: ne } = productBounds;
    selectPoint({ lng: sw[0] + (x - image.left) / image.width * (ne[0] - sw[0]),
      lat: ne[1] - (y - image.top) / image.height * (ne[1] - sw[1]) });
  }
}

async function loadWorkspace() {
  errorMessage.value = '';
  try {
    // Always load the shipped Jiefangzha dataset first. A failed/partial
    // request for an unrelated project must not prevent the default dataset
    // from appearing on the Explore screen.
    const [polygonResponse, resultResponse] = await Promise.all([
      api.get('/api/polygons/83/'),
      api.get('/api/polygons/83/result-set-list/'),
    ]);
    const defaultResult = (resultResponse.data || []).find((item) => Number(item.result_set_id) === 83)
      || (resultResponse.data || []).find((item) => String(item.status || '').toLowerCase() === 'completed')
      || (resultResponse.data || [])[0];
    if (!defaultResult) throw new Error('The default Jiefangzha result set is not available.');
    polygonId.value = 83;
    resultSetId.value = Number(defaultResult.result_set_id);
    emit('api-status', true);
    polygonName.value = polygonResponse.data.name;
    polygonCoordinates = polygonResponse.data.gcj02_coordinates || [];
    resultStatus.value = String(defaultResult.status || 'ready').toUpperCase();
    const filesResponse = await api.get(`/api/result_img/${resultSetId.value}/list/`);
    dates.value = filesResponse.data.files;
    selectedDate.value = dates.value[0] || '';
    drawBoundary();
    if (selectedDate.value) await selectDate(selectedDate.value);

    const defaultProject = {
      ...defaultResult,
      id: Number(defaultResult.result_set_id),
      polygon_id: 83,
      name: polygonResponse.data.name || 'jiefangzha',
      isDefault: true,
    };

    try {
      const polygonsResponse = await api.get('/api/polygons/');
      const otherPolygons = (polygonsResponse.data || []).filter((polygon) => Number(polygon.id) !== 83);
      const projectGroups = await Promise.all(otherPolygons.map(async (polygon) => {
        try {
          const response = await api.get(`/api/polygons/${polygon.id}/result-set-list/`);
          return (response.data || []).filter((item) => item.status !== 'deleted').map((item) => ({
            ...item, id: item.result_set_id, polygon_id: polygon.id, name: polygon.name,
          }));
        } catch {
          return [];
        }
      }));
      projectOptions.value = [defaultProject, ...projectGroups.flat()];
    } catch {
      // The project picker is secondary. Keep the already loaded Jiefangzha
      // map available if listing another project fails.
      projectOptions.value = [defaultProject];
    }

    // Generate links to Explore with the newly created result-set id. Once
    // the project list is available, switch to that result automatically.
    const requestedResultId = Number(route.query.result);
    if (Number.isFinite(requestedResultId) && requestedResultId > 0 && requestedResultId !== resultSetId.value) {
      const requestedProject = projectOptions.value.find((project) => Number(project.result_set_id) === requestedResultId);
      if (requestedProject) await selectProject(requestedProject);
    }
  } catch (error) {
    emit('api-status', false);
    errorMessage.value = error.response?.data?.detail || error.message || 'Unable to load the FieldMoist dataset.';
  }
}

async function selectProject(project) {
  projectsOpen.value = false;
  imageRequest++;
  fallbackImageUrl.value = '';
  productBounds = null;
  if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
  imageObjectUrl = null;
  clearInterval(playbackTimer);
  playing.value = false;
  selectedPoint.value = null;
  weatherData.value = null;
  seriesReady.value = false;
  dates.value = [];
  selectedDate.value = '';
  polygonId.value = project.polygon_id;
  resultSetId.value = project.result_set_id;
  const [polygonResponse, filesResponse] = await Promise.all([
    api.get(`/api/polygons/${project.polygon_id}/`),
    api.get(`/api/result_img/${project.result_set_id}/list/`),
  ]);
  polygonName.value = polygonResponse.data.name;
  polygonCoordinates = polygonResponse.data.gcj02_coordinates || [];
  dates.value = filesResponse.data.files;
  selectedDate.value = dates.value[0] || '';
  resultStatus.value = String(project.status || 'ready').toUpperCase();
  drawBoundary();
  if (selectedDate.value) await selectDate(selectedDate.value);
}

async function deleteProject(project) {
  if (project?.isDefault || Number(project?.polygon_id) === 83) return;
  if (!window.confirm(`Delete ${project.name} (${project.start_date} to ${project.end_date}) permanently?`)) return;
  try {
    await api.delete(`/api/result_img/${project.result_set_id}/?purge=true`);
    projectOptions.value = projectOptions.value.filter((item) => item.result_set_id !== project.result_set_id);
    if (project.result_set_id === resultSetId.value) {
      const next = projectOptions.value[0];
      if (next) await selectProject(next);
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'Unable to delete the project.';
  }
}

async function selectDate(date) {
  if (!date || !dates.value.includes(date) || !resultSetId.value) return;
  selectedDate.value = date;
  loadingImage.value = true;
  errorMessage.value = '';
  const request = ++imageRequest;
  try {
    fallbackImageUrl.value = '';
    const metadataKey = `fieldmoist:png:${resultSetId.value}:${date}`;
    let product = null;
    try {
      const response = await api.get(`/api/result_img/${resultSetId.value}/get_png/`, { params: { date } });
      product = response.data;
      try { localStorage.setItem(metadataKey, JSON.stringify(product)); } catch { /* Storage may be disabled. */ }
    } catch (requestError) {
      try { product = JSON.parse(localStorage.getItem(metadataKey) || 'null'); } catch { product = null; }
      if (!product?.png_url || !product?.bounds) throw requestError;
    }
    const url = await getCachedProductImageUrl(new URL(product.png_url, api.defaults.baseURL).href);
    if (disposed || request !== imageRequest) {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url);
      return;
    }
    if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
    imageObjectUrl = url.startsWith('blob:') ? url : null;
    productBounds = product.bounds.gcj02;
    fallbackImageUrl.value = url;
    positionProductImage();
  } catch (error) {
    if (request === imageRequest) errorMessage.value = error.response?.data?.error || `Unable to load the product for ${date}.`;
  } finally {
    if (request === imageRequest) loadingImage.value = false;
  }
}

async function getCachedProductImageUrl(url) {
  if (!('caches' in window)) return url;
  try {
    const cache = await caches.open('fieldmoist-products-v2');
    try {
      const response = await fetch(url, { mode: 'cors', cache: 'no-store' });
      if (!response.ok) return url;
      try { await cache.put(url, response.clone()); } catch { /* Cache quota must not hide a valid image. */ }
      return URL.createObjectURL(await response.blob());
    } catch {
      const cached = await cache.match(url);
      return cached ? URL.createObjectURL(await cached.blob()) : url;
    }
  } catch {
    return url;
  }
}

function stepDate(offset) {
  const nextIndex = Math.min(Math.max(dateIndex.value + offset, 0), dates.value.length - 1);
  if (nextIndex >= 0) selectDate(dates.value[nextIndex]);
}

function togglePlayback() {
  playing.value = !playing.value;
  if (!playing.value) {
    clearInterval(playbackTimer);
    return;
  }
  playbackTimer = setInterval(() => {
    if (dateIndex.value >= dates.value.length - 1) {
      playing.value = false;
      clearInterval(playbackTimer);
    } else {
      stepDate(1);
    }
  }, 1200);
}

async function loadTimeSeries() {
  if (!selectedPoint.value) return;
  loadingSeries.value = true;
  errorMessage.value = '';
  try {
    const response = await api.get('/api/weather_data/', {
      params: {
        latitude: selectedPoint.value.lat,
        longitude: selectedPoint.value.lng,
        start_date: firstDate.value,
        end_date: lastDate.value,
        result_set_id: resultSetId.value,
        coordinate_system: 'gcj02',
      },
      timeout: 90000,
    });
    if (!response.data?.success) {
      throw new Error(response.data?.message || 'Point analysis returned no data.');
    }
    weatherData.value = response.data;
    seriesReady.value = true;
    await nextTick();
    await renderChart(response.data);
  } catch (error) {
    errorMessage.value = error.response?.data?.message || 'Unable to retrieve the point time series.';
  } finally {
    loadingSeries.value = false;
  }
}

async function renderChart(data) {
  const echarts = await import('echarts');
  chart ||= echarts.init(chartElement.value);
  chart.setOption({
    animation: false,
    grid: { left: 46, right: 16, top: 34, bottom: 50 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—',
    },
    legend: { data: ['Soil moisture', 'Rainfall'], top: 2, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: data.dates, axisLabel: { fontSize: 9, hideOverlap: true } },
    yAxis: [
      { type: 'value', name: 'm³/m³', nameTextStyle: { fontSize: 9 }, axisLabel: { fontSize: 9 } },
      { type: 'value', name: 'mm', nameTextStyle: { fontSize: 9 }, axisLabel: { fontSize: 9 } },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 8 }],
    series: [
      { name: 'Soil moisture', type: 'line', data: data.series.moisture, symbol: 'none', lineStyle: { width: 1.5, color: '#246a44' } },
      { name: 'Rainfall', type: 'bar', yAxisIndex: 1, data: data.series.rain, itemStyle: { color: '#5b8fb9' }, large: true },
    ],
  });
}

function downloadTif() {
  const href = new URL(`/api/result_img/${resultSetId.value}/get_tif/?date=${selectedDate.value}`, api.defaults.baseURL).href;
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = `${selectedDate.value}.tif`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function handleResize() {
  positionProductImage();
  map?.resize();
  chart?.resize();
}

onMounted(async () => {
  window.addEventListener('resize', handleResize);
  await Promise.all([initializeMap(), loadWorkspace()]);
});

onBeforeUnmount(() => {
  disposed = true;
  imageRequest++;
  clearInterval(playbackTimer);
  stopNasaCoveragePolling();
  window.removeEventListener('resize', handleResize);
  chart?.dispose();
  if (imageObjectUrl) URL.revokeObjectURL(imageObjectUrl);
  map?.destroy();
});
</script>

<style scoped>
.workspace { height: calc(100vh - 64px); min-height: 650px; display: grid; grid-template-columns: minmax(0, 1fr) 390px; overflow: hidden; }
.map-stage { position: relative; min-width: 0; overflow: hidden; background: #dfe5e1; }
.map-canvas { position: absolute; inset: 0; }
.product-fallback-image { position: absolute; inset: 15% 8%; z-index: 10; width: 84%; height: 70%; object-fit: contain; pointer-events: none; }
.selected-point-marker { position: absolute; z-index: 26; width: 20px; height: 20px; box-sizing: border-box; border: 3px solid white; border-radius: 50%; background: #d64c3f; box-shadow: 0 1px 6px rgb(0 0 0 / 55%); transform: translate(-50%, -50%); pointer-events: none; }
.selected-point-marker span { position: absolute; inset: 4px; border-radius: 50%; background: white; }
.point-capture-layer { position: absolute; z-index: 25; inset: 0; cursor: crosshair; }
.basemap-switch { position: absolute; z-index: 30; top: 20px; right: 20px; display: inline-flex; align-items: center; gap: 4px; padding: 4px; background: rgb(255 255 255 / 94%); border: 1px solid #d8dfdb; box-shadow: 0 3px 14px rgb(23 32 29 / 14%); }
.switch-label { padding: 0 6px; color: #607069; font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.switch-button { min-height: 30px; display: inline-flex; align-items: center; gap: 5px; padding: 0 8px; color: #46534d; background: transparent; border: 1px solid transparent; border-radius: 3px; font-size: 10px; font-weight: 650; }
.switch-button:hover { background: #edf3ef; }
.switch-button.active { color: #fff; background: #286443; border-color: #286443; }
.map-heading { position: absolute; z-index: 30; top: 20px; left: 20px; padding: 13px 15px; background: rgb(255 255 255 / 92%); border-left: 3px solid #427256; box-shadow: 0 4px 18px rgb(23 32 29 / 14%); }
.monitoring-label { display: flex; align-items: center; gap: 6px; }
.project-toggle { width: 20px; height: 20px; padding: 0; color: #427256; background: transparent; border: 0; cursor: pointer; }
.project-menu { position: absolute; top: 100%; left: -3px; min-width: 300px; margin-top: 8px; padding: 6px; color: #2e3d35; background: #fff; border: 1px solid #d8dfdb; box-shadow: 0 5px 18px rgb(23 32 29 / 18%); }
.project-item { display: flex; align-items: center; gap: 6px; border-bottom: 1px solid #edf1ee; }
.project-item:last-child { border-bottom: 0; }
.project-name { flex: 1; padding: 8px 6px; color: #33463b; background: transparent; border: 0; text-align: left; font-size: 11px; cursor: pointer; }
.project-name:hover { background: #f1f6f2; }
.project-delete { width: 28px; height: 28px; padding: 0; color: #a14b3c; background: transparent; border: 0; cursor: pointer; }
.project-delete:disabled { color: #aeb8b2; cursor: not-allowed; opacity: .65; }
.project-empty { padding: 8px; color: #68756f; font-size: 11px; }
.eyebrow { display: block; color: #607069; font-size: 10px; font-weight: 750; letter-spacing: .11em; }
.map-heading h1 { margin: 3px 0 2px; font-size: 21px; line-height: 1.15; text-transform: capitalize; }
.map-heading p { margin: 0; color: #5d6964; font-size: 11px; }
.legend { position: absolute; z-index: 30; right: 20px; bottom: 20px; width: 220px; padding: 10px 12px; background: rgb(255 255 255 / 94%); box-shadow: 0 3px 14px rgb(23 32 29 / 14%); }
.legend-title { display: block; margin-bottom: 7px; color: #39433f; font-size: 10px; }
.legend-title b { float: right; font-weight: 500; }
.legend-scale { height: 10px; background: linear-gradient(to right, rgb(213, 38, 40), rgb(254, 254, 254) 50%, rgb(31, 119, 180)); border: 1px solid #d3d8d5; }
.legend-labels { display: flex; justify-content: space-between; margin-top: 4px; color: #46514c; font-size: 9px; }
.map-message, .map-loading { position: absolute; z-index: 31; left: 50%; transform: translateX(-50%); display: flex; gap: 8px; align-items: center; background: #17201d; color: white; padding: 10px 14px; font-size: 12px; box-shadow: 0 5px 20px rgb(0 0 0 / 22%); }
.map-message { bottom: 20px; left: 20px; transform: none; max-width: calc(100% - 250px); }
.map-loading { bottom: 20px; }
.inspector { overflow-y: auto; padding: 20px; background: #f8faf9; border-left: 1px solid #d8ddda; }
.section-header, .panel-title, .action-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.section-header { padding-bottom: 16px; border-bottom: 1px solid #dfe4e1; }
h2 { margin: 4px 0 0; font-size: 19px; }
h3 { margin: 3px 0 0; font-size: 15px; }
.quality-badge { padding: 5px 7px; color: #2e6846; background: #e4f0e8; border: 1px solid #c7ddce; border-radius: 4px; font-size: 10px; font-weight: 700; }
.date-control { margin: 18px 0 14px; display: grid; grid-template-columns: 36px minmax(0, 1fr) 36px 36px; gap: 7px; align-items: end; }
.date-control label span { display: block; margin-bottom: 5px; color: #66736d; font-size: 10px; font-weight: 650; }
.date-control input { width: 100%; height: 36px; padding: 0 9px; color: #25302b; background: white; border: 1px solid #cdd5d1; border-radius: 4px; }
.icon-button { width: 36px; height: 36px; display: grid; place-items: center; color: #34413b; background: white; border: 1px solid #cdd5d1; border-radius: 4px; }
.icon-button:hover:not(:disabled) { background: #edf3ef; border-color: #87a793; }
button:disabled { cursor: not-allowed; opacity: .45; }
.location-panel { margin-top: 18px; padding-top: 17px; border-top: 1px solid #dfe4e1; }
.panel-title > i { color: #527363; font-size: 18px; }
.empty-copy { min-height: 54px; margin: 12px 0; color: #68756f; font-size: 12px; line-height: 1.55; }
.coordinate-row { display: flex; justify-content: space-between; margin: 12px 0 9px; padding: 9px 10px; background: #edf1ef; color: #44514b; font-size: 11px; font-variant-numeric: tabular-nums; }
.coordinate-row small { color: #728079; font-size: 9px; }
.primary-button, .secondary-button { min-height: 36px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: 4px; font-weight: 650; font-size: 12px; }
.primary-button { width: 100%; color: white; background: #286443; border: 1px solid #286443; }
.primary-button:hover:not(:disabled) { background: #1f5136; }
.analysis-button { width: 100%; min-height: 36px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; margin: 12px 0 2px; color: #2d493a; background: white; border: 1px solid #9caf9f; border-radius: 4px; font-size: 12px; font-weight: 650; }
.analysis-button:hover { background: #edf3ef; }
.analysis-button.active { color: white; background: #286443; border-color: #286443; }
.nasa-region-download { margin: 9px 0 3px; padding: 9px 10px; background: #edf3ef; border-left: 3px solid #5a8668; }
.nasa-region-button { width: 100%; }
.nasa-region-download small { display: block; margin-top: 5px; color: #68756f; font-size: 10px; }
.nasa-region-status { color: #5f6d66; font-size: 10px; line-height: 1.4; }
.nasa-region-status.complete { color: #286243; font-weight: 650; }
.secondary-button { flex: 1; color: #2d493a; background: white; border: 1px solid #9caf9f; }
.secondary-button:hover:not(:disabled) { background: #edf3ef; }
.series-chart { width: 100%; height: 245px; margin-top: 14px; background: white; border: 1px solid #dfe4e1; }
.weather-panel { margin-top: 16px; padding-top: 14px; border-top: 1px solid #dfe4e1; }
.weather-title { margin-bottom: 10px; }
.weather-title > i { color: #527363; font-size: 18px; }
.weather-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
.weather-grid > div { padding: 9px; background: white; border: 1px solid #dfe4e1; }
.weather-grid span, .weather-grid small { display: block; color: #6c7772; font-size: 9px; }
.weather-grid strong { display: block; margin: 4px 0 2px; color: #2d493a; font-size: 15px; font-variant-numeric: tabular-nums; }
.weather-warning { margin: 9px 0 0; color: #766a44; font-size: 10px; line-height: 1.4; }
.nasa-source { margin: 9px 0 0; color: #68756f; font-size: 10px; }
.error-message { margin-top: 14px; padding: 10px; color: #8a3428; background: #fae9e5; border-left: 3px solid #d86651; font-size: 11px; line-height: 1.45; }
.action-row { display: flex; align-items: center; gap: 8px; margin-top: 18px; }
.action-row .secondary-button { min-width: 0; }
.metadata { margin-top: 17px; padding-top: 12px; display: flex; flex-wrap: wrap; gap: 7px 13px; border-top: 1px solid #dfe4e1; color: #77817d; font-size: 9px; }

@media (max-width: 900px) {
  .workspace { height: auto; min-height: calc(100vh - 58px); grid-template-columns: 1fr; overflow: visible; }
  .map-stage { height: 58vh; min-height: 420px; }
  .inspector { overflow: visible; border-left: 0; border-top: 1px solid #d8ddda; }
}
@media (max-width: 520px) {
  .workspace { min-height: calc(100vh - 58px); }
  .map-stage { min-height: 390px; }
  .map-heading { top: 64px; left: 12px; }
  .basemap-switch { top: 12px; right: 12px; }
  .switch-label { display: none; }
  .map-message { top: auto; bottom: 12px; left: 12px; max-width: calc(100% - 210px); justify-content: center; text-align: center; }
  .map-loading { top: 112px; bottom: auto; width: calc(100% - 24px); justify-content: center; }
  .legend { right: 12px; bottom: 12px; width: 190px; }
  .inspector { padding: 16px; }
  .action-row { flex-wrap: wrap; }
  .action-row .secondary-button { flex: 1 1 145px; }
}
</style>
