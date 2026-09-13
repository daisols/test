<template>
  <div class="generation-workspace">
    <div v-if="completionNoticeVisible" class="completion-toast" role="status" aria-live="polite">
      <div class="completion-toast-title"><i class="fa-solid fa-circle-check" /> Project generated successfully</div>
      <div class="completion-toast-track"><span :style="{ width: `${completionNoticeProgress}%` }" /></div>
    </div>
    <section class="boundary-map">
      <div ref="mapElement" :class="{ 'drawing-cursor': mode === 'map' }" class="map-canvas" />
      <div class="basemap-switch" role="group" aria-label="Basemap selection">
        <span class="switch-label">Basemap</span>
        <button :class="['switch-button', { active: basemapMode === 'satellite' }]" type="button" @click="setBasemap('satellite')">
          <i class="fa-solid fa-satellite" /> Satellite
        </button>
        <button :class="['switch-button', { active: basemapMode === 'standard' }]" type="button" @click="setBasemap('standard')">
          <i class="fa-solid fa-map" /> Standard
        </button>
      </div>
      <div class="map-instruction">
        <span class="eyebrow">BOUNDARY EDITOR</span>
        <strong>{{ mode === 'map' ? 'Click the map to add field vertices' : mode === 'coordinates' ? 'WGS84 coordinate input selected' : 'SHP boundary upload selected' }}</strong>
        <small v-if="mode === 'map'">{{ mapPoints.length }} vertices · minimum 3</small>
      </div>
      <div v-if="mapMessage" class="map-message"><i class="fa-solid fa-circle-info" /> {{ mapMessage }}</div>
      <div class="map-tools" v-if="mode === 'map'">
        <button title="Undo last vertex" aria-label="Undo last vertex" :disabled="!mapPoints.length" @click="undoPoint"><i class="fa-solid fa-rotate-left" /></button>
        <button title="Clear boundary" aria-label="Clear boundary" :disabled="!mapPoints.length" @click="clearPoints"><i class="fa-solid fa-trash" /></button>
      </div>
    </section>

    <aside class="generation-panel">
      <header>
        <span class="eyebrow">PRODUCT GENERATION</span>
        <h1>New processing job</h1>
        <p>Define a farmland boundary and date range. FieldMoist will retrieve source imagery and run the soil-moisture workflow in the background.</p>
      </header>

      <form @submit.prevent="submitJob">
        <fieldset>
          <legend>Processing mode</legend>
          <div class="segmented">
            <button type="button" :class="{ active: generationMode === 'online' }" @click="generationMode = 'online'"><i class="fa-solid fa-cloud-arrow-down" /> Online</button>
            <button type="button" :class="{ active: generationMode === 'offline' }" @click="generationMode = 'offline'"><i class="fa-solid fa-hard-drive" /> Offline</button>
          </div>
        </fieldset>
        <div class="field">
          <label for="area-name">Area name</label>
          <input id="area-name" v-model.trim="name" @blur="maybeUploadShp" required maxlength="100" placeholder="e.g. north-field" />
        </div>

        <div v-if="generationMode === 'offline'" class="offline-inputs">
          <div class="field"><label for="offline-smap">Local SMAP GeoTIFF files</label><div v-if="testPreset" class="preset-path">{{ testPreset.smap_path }}</div><input v-else id="offline-smap" type="file" multiple accept=".tif,.tiff" @change="setOfflineFiles('smap', $event)" /></div>
          <div class="field"><label for="offline-s1">Local Sentinel-1 GeoTIFF files</label><input v-if="!testPreset" id="offline-s1" type="file" multiple accept=".tif,.tiff" @change="setOfflineFiles('sentinel-1', $event)" /><div v-else class="preset-path muted">Not used by the test preset</div></div>
          <div class="field"><label for="offline-s2">Local Sentinel-2 GeoTIFF files</label><input v-if="!testPreset" id="offline-s2" type="file" multiple accept=".tif,.tiff" @change="setOfflineFiles('sentinel-2', $event)" /><div v-else class="preset-path muted">Not used by the test preset</div></div>
          <div class="field"><label for="offline-moisture">Precomputed soil-moisture GeoTIFF files (optional)</label><div v-if="testPreset" class="preset-path">{{ testPreset.local_moisture_path }}</div><input v-else id="offline-moisture" type="file" multiple accept=".tif,.tiff" @change="localMoistureFiles = Array.from($event.target.files || [])" /><small v-if="localMoistureFiles.length">{{ localMoistureFiles.length }} soil-moisture files selected. Sentinel-1/2 uploads are optional when these files are supplied.</small></div>
          <small v-if="!testPreset">Each filename must include its satellite type and date, for example sentinel-1_2018-05-01.tif.</small>
          <small v-else>Shared model: {{ testPreset.model_path }}</small>
        </div>
        <fieldset>
          <legend>Boundary source</legend>
          <div class="segmented">
            <button type="button" :class="{ active: mode === 'map' }" @click="mode = 'map'"><i class="fa-solid fa-location-dot" /> Map clicks</button>
            <button type="button" :class="{ active: mode === 'coordinates' }" @click="mode = 'coordinates'"><i class="fa-solid fa-list-ol" /> WGS84 coordinates</button>
            <button type="button" :class="{ active: mode === 'shp' }" @click="mode = 'shp'"><i class="fa-solid fa-file-zipper" /> SHP file</button>
          </div>
        </fieldset>

        <div v-if="mode === 'coordinates'" class="field">
          <label for="coordinates">Longitude, latitude · one vertex per line</label>
          <textarea id="coordinates" v-model="coordinateText" rows="7" placeholder="107.1000, 40.8000&#10;107.2000, 40.8000&#10;107.1500, 40.9000" />
          <small>{{ parsedCoordinates.length }} valid vertices</small>
        </div>

        <div v-if="mode === 'shp'" class="field">
          <label for="shp-files">Shapefile bundle</label>
          <div v-if="testPreset" class="preset-path">{{ testPreset.shp_path }}</div>
          <template v-else>
            <input id="shp-files" ref="shpInput" type="file" multiple accept=".zip,.shp,.shx,.dbf,.prj,.cpg" @change="handleShpFiles" />
            <small>Upload one ZIP containing the SHP components, or select the matching .shp, .shx, .dbf and .prj files together.</small>
            <small v-if="shpFiles.length">{{ shpFiles.map((file) => file.name).join(', ') }}</small>
          </template>
          <small v-if="shpUploading">Uploading boundary...</small>
        </div>

        <div class="date-grid">
          <div class="field"><label for="start-date">Start date</label><input id="start-date" v-model.trim="startDate" :class="{ 'preset-date': testPreset }" required inputmode="numeric" pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" /></div>
          <div class="field"><label for="end-date">End date</label><input id="end-date" v-model.trim="endDate" :class="{ 'preset-date': testPreset }" required inputmode="numeric" pattern="\d{4}-\d{2}-\d{2}" placeholder="YYYY-MM-DD" /></div>
        </div>

        <div class="field measured-input"><label for="measurement-excel">Station coordinate Excel file (optional)</label><div v-if="testPreset" class="preset-path">{{ testPreset.measurement_excel_display_path }}</div><input v-else id="measurement-excel" type="file" accept=".xls,.xlsx" @change="measurementExcel = $event.target.files?.[0] || null" /><small v-if="measurementExcel">{{ measurementExcel.name }} · patches only the listed station pixels</small><small v-else-if="!testPreset">Required columns: <strong>lon</strong> (longitude) and <strong>lat</strong> (latitude). <strong>Time</strong> and <strong>MSM</strong> are only needed when no compatible pre-trained model is available.</small></div>

        <div v-if="generationMode === 'online'" class="notice"><i class="fa-solid fa-cloud-arrow-down" /><span>This job requires Google Earth Engine authentication and network access. 中国境内网络可能无法连接到 GEE，请注意网络环境。</span></div>
        <div v-if="feedback" class="feedback" :class="feedbackType"><i :class="feedbackType === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-triangle-exclamation'" /> {{ feedback }}</div>
        <div v-if="jobId" class="job-progress" :class="jobStatusClass">
          <div class="job-progress-head"><span>{{ jobStatusLabel }}</span><strong>{{ jobProgress }}%</strong></div>
          <div class="progress-track" role="progressbar" :aria-valuenow="jobProgress" aria-valuemin="0" aria-valuemax="100"><span :style="{ width: `${jobProgress}%` }" /></div>
          <small v-if="jobId">Job {{ jobId }}</small>
          <small v-if="jobError" class="job-error">{{ jobError }}</small>
        </div>
        <div v-if="testPreset" class="test-preset-hint"><i class="fa-solid fa-circle-check" /> Offline test dataset is ready. Click Start generation.</div>
        <button v-if="testPreset && jobId && (jobStatus === 'completed' || jobStatus === 'failed')" class="test-rerun-button" :disabled="rerunning" type="button" @click="rerunTest">
          <i :class="rerunning ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-rotate-right'" />
          {{ rerunning ? 'Restarting test project' : 'Run test again' }}
        </button>
        <button class="submit-button" :class="{ completed: jobStatus === 'completed' }" :disabled="submitting || !canSubmit || jobStatus === 'completed'" type="submit">
          <i :class="submitting ? 'fa-solid fa-spinner fa-spin' : 'fa-solid fa-gears'" />
          {{ submitting ? 'Creating processing job' : jobStatus === 'completed' ? 'Project generated successfully' : 'Start generation' }}
        </button>
        <div v-if="jobStatus === 'completed'" class="completion-actions">
          <button class="secondary-action" type="button" @click="startNewProject"><i class="fa-solid fa-plus" /> Start a new project</button>
          <button class="primary-action" type="button" @click="viewGeneratedResult"><i class="fa-solid fa-map" /> View generated result</button>
        </div>
      </form>
    </aside>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import AMapLoader from '@amap/amap-jsapi-loader';
import api from '../services/axios.js';

const emit = defineEmits(['api-status']);
const router = useRouter();
const mapElement = ref(null);
const mode = ref('map');
const name = ref('');
const generationMode = ref('online');
const offlineFiles = ref({ 'sentinel-1': [], 'sentinel-2': [], smap: [] });
const localMoistureFiles = ref([]);
const measurementExcel = ref(null);
const startDate = ref('');
const endDate = ref('');
const coordinateText = ref('');
const mapPoints = ref([]);
const shpFiles = ref([]);
const shpInput = ref(null);
const shpUploading = ref(false);
const uploadedPolygon = ref(null);
const mapMessage = ref('');
const submitting = ref(false);
const feedback = ref('');
const feedbackType = ref('error');
const basemapMode = ref('satellite');
const jobId = ref(null);
const jobProgress = ref(0);
const jobStatus = ref('');
const jobError = ref('');
const testPreset = ref(null);
const loadingTestPreset = ref(false);
const rerunning = ref(false);
const completionNoticeVisible = ref(false);
const completionNoticeProgress = ref(0);
let progressTimer = null;
let completionNoticeTimer = null;
let map = null;
let AMap = null;
let preview = null;
let satelliteLayer = null;
let standardLayer = null;

const parsedCoordinates = computed(() => coordinateText.value.split(/\r?\n/).map((line) => line.split(',').map(Number)).filter((point) => point.length === 2 && point.every(Number.isFinite)));
const activeCoordinates = computed(() => mode.value === 'map' ? mapPoints.value : mode.value === 'coordinates' ? parsedCoordinates.value : shpFiles.value);
const boundaryReady = computed(() => mode.value === 'shp'
  ? (Boolean(testPreset.value) || (shpFiles.value.length > 0 && !shpUploading.value && Boolean(uploadedPolygon.value)))
  : activeCoordinates.value.length >= 3);
const datePattern = /^\d{4}-\d{2}-\d{2}$/;
const canSubmit = computed(() => name.value && datePattern.test(startDate.value) && datePattern.test(endDate.value) && startDate.value <= endDate.value && boundaryReady.value && (generationMode.value === 'online' || Boolean(testPreset.value) || (offlineFiles.value.smap.length >= 2 && (localMoistureFiles.value.length > 0 || (offlineFiles.value['sentinel-1'].length >= 2 && offlineFiles.value['sentinel-2'].length >= 2)))));
const jobStatusLabel = computed(() => ({
  Waiting: 'Queued', waiting: 'Queued', queued: 'Queued', downloading: 'Downloading data',
  filtering: 'Preprocessing data', preprocessing: 'Preprocessing data', solving: 'Solving soil moisture',
  processing: 'Solving soil moisture', colorizing: 'Generating map images', completed: 'Completed', failed: 'Failed',
}[jobStatus.value] || 'Preparing task'));
const jobStatusClass = computed(() => jobStatus.value === 'failed' ? 'failed' : jobStatus.value === 'completed' ? 'completed' : 'running');

function displayPolygonBoundary(polygon) {
  const coordinates = polygon?.gcj02_coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 3) return;
  mapPoints.value = coordinates
    .map((point) => [Number(point?.[0]), Number(point?.[1])])
    .filter((point) => point.every(Number.isFinite));
  renderPreview();
  if (map && preview) map.setFitView([preview]);
}

async function uploadShpBoundary() {
  if (mode.value !== 'shp' || !name.value || !shpFiles.value.length || shpUploading.value) return;
  shpUploading.value = true;
  uploadedPolygon.value = null;
  feedback.value = '';
  try {
    // Reuse an existing named area instead of creating a duplicate polygon.
    const polygonsResponse = await api.get('/api/polygons/');
    const existingPolygon = (polygonsResponse.data || []).find((polygon) => polygon.name === name.value);
    if (existingPolygon) {
      uploadedPolygon.value = existingPolygon;
      displayPolygonBoundary(existingPolygon);
      feedbackType.value = 'success';
      feedback.value = `Boundary for ${name.value} is ready.`;
      return;
    }

    const formData = new FormData();
    formData.append('name', name.value);
    shpFiles.value.forEach((file) => formData.append('files', file));
    const response = await api.post('/api/polygons/from-shp/', formData);
    uploadedPolygon.value = response.data;
    displayPolygonBoundary(response.data);
    feedbackType.value = 'success';
    feedback.value = 'SHP boundary uploaded and displayed.';
  } catch (error) {
    feedbackType.value = 'error';
    const details = error.response?.data;
    feedback.value = typeof details === 'string' ? details : JSON.stringify(details || error.message);
  } finally {
    shpUploading.value = false;
  }
}

async function loadTestPreset() {
  if (generationMode.value !== 'offline' || name.value.toLowerCase() !== 'test' || loadingTestPreset.value) return;
  loadingTestPreset.value = true;
  try {
    const response = await api.get('/api/result_img/offline-test-preset/');
    testPreset.value = response.data;
    // The preset is server-side; clear any previously selected browser files
    // so the request uses the bundled Dataset 82 inputs exclusively.
    offlineFiles.value = { 'sentinel-1': [], 'sentinel-2': [], smap: [] };
    localMoistureFiles.value = [];
    measurementExcel.value = null;
    name.value = response.data.name || 'test';
    startDate.value = response.data.start_day;
    endDate.value = response.data.end_day;
    mode.value = 'shp';
    uploadedPolygon.value = {
      id: Number(response.data.polygon_id),
      name: response.data.name || 'test',
      gcj02_coordinates: response.data.gcj02_coordinates,
      wgs84_coordinates: response.data.wgs84_coordinates,
    };
    mapPoints.value = (response.data.gcj02_coordinates || []).map((point) => [Number(point[0]), Number(point[1])]);
    renderPreview();
    if (map && preview) map.setFitView([preview]);
    feedback.value = '';
    feedbackType.value = 'success';
  } catch (error) {
    testPreset.value = null;
    feedbackType.value = 'error';
    feedback.value = error.response?.data?.detail || `Unable to load the offline test dataset: ${error.message}`;
  } finally {
    loadingTestPreset.value = false;
  }
}

function maybeUploadShp() {
  if (mode.value === 'shp' && shpFiles.value.length && name.value && !uploadedPolygon.value) uploadShpBoundary();
}

function handleShpFiles(event) {
  shpFiles.value = Array.from(event.target.files || []);
  uploadedPolygon.value = null;
  feedback.value = '';
  if (shpFiles.value.length && !name.value) {
    feedbackType.value = 'error';
    feedback.value = 'Enter an area name before uploading the SHP boundary.';
    return;
  }
  uploadShpBoundary();
}

function setOfflineFiles(satellite, event) {
  offlineFiles.value = { ...offlineFiles.value, [satellite]: Array.from(event.target.files || []) };
}

async function initializeMap() {
  const key = import.meta.env.VITE_AMAP_KEY;
  if (!key) {
    mapMessage.value = 'Configure VITE_AMAP_KEY to draw a boundary, or use WGS84 coordinate input.';
    return;
  }
  if (import.meta.env.VITE_AMAP_SECURITY_CODE) window._AMapSecurityConfig = { securityJsCode: import.meta.env.VITE_AMAP_SECURITY_CODE };
  try {
    AMap = await AMapLoader.load({ key, version: '2.0', plugins: ['AMap.Scale', 'AMap.ToolBar'] });
    satelliteLayer = new AMap.TileLayer.Satellite();
    standardLayer = new AMap.TileLayer();
    standardLayer.setOpacity(0);
    map = new AMap.Map(mapElement.value, {
      viewMode: '2D',
      zoom: 8,
      center: [107.04, 40.86],
      layers: [satelliteLayer, standardLayer],
    });
    map.addControl(new AMap.Scale());
    map.on('click', (event) => {
      if (mode.value !== 'map') return;
      mapPoints.value.push([event.lnglat.lng, event.lnglat.lat]);
      renderPreview();
    });
    if (mapPoints.value.length >= 3) {
      renderPreview();
      if (preview) map.setFitView([preview]);
    }
  } catch (error) {
    mapMessage.value = `Boundary map initialization failed: ${error.message}`;
  }
}

function setBasemap(mode) {
  basemapMode.value = mode;
  if (!map || !satelliteLayer || !standardLayer) return;
  satelliteLayer.setOpacity(mode === 'satellite' ? 1 : 0);
  standardLayer.setOpacity(mode === 'standard' ? 1 : 0);
  // Both basemap layers are attached at map creation. Changing opacity keeps
  // the boundary preview and any other overlays in the map layer stack.
}

function renderPreview() {
  if (!map || !AMap) return;
  if (preview) map.remove(preview);
  if (!mapPoints.value.length) return;
  preview = mapPoints.value.length >= 3
    ? new AMap.Polygon({ path: mapPoints.value, strokeColor: '#375e48', strokeWeight: 1, fillColor: '#70a182', fillOpacity: 0.16 })
    : new AMap.Polyline({ path: mapPoints.value, strokeColor: '#375e48', strokeWeight: 2 });
  map.add(preview);
}

function undoPoint() { mapPoints.value.pop(); renderPreview(); }
function clearPoints() { mapPoints.value = []; if (preview && map) map.remove(preview); preview = null; }

async function submitJob() {
  submitting.value = true;
  feedback.value = '';
  jobError.value = '';
  try {
    let polygonResponse;
    if (mode.value === 'shp') {
      if (testPreset.value) {
        polygonResponse = { data: uploadedPolygon.value };
      } else {
      if (!uploadedPolygon.value) await uploadShpBoundary();
      if (!uploadedPolygon.value) throw new Error('Upload the SHP boundary before starting generation.');
      polygonResponse = { data: uploadedPolygon.value };
      }
    } else {
      const polygonsResponse = await api.get('/api/polygons/');
      const existingPolygon = (polygonsResponse.data || []).find((polygon) => polygon.name === name.value);
      if (existingPolygon) {
        polygonResponse = { data: existingPolygon };
      } else {
        const boundaryPayload = mode.value === 'map'
          ? { gcj02_coordinates: mapPoints.value }
          : { wgs84_coordinates: parsedCoordinates.value };
        polygonResponse = await api.post('/api/polygons/', { name: name.value, ...boundaryPayload });
      }
    }
    let payload;
    let requestConfig;
    if (generationMode.value === 'offline') {
      payload = new FormData();
      payload.append('polygon', polygonResponse.data.id);
      payload.append('start_day', startDate.value);
      payload.append('end_day', endDate.value);
      payload.append('generation_mode', 'offline');
      Object.entries(offlineFiles.value).forEach(([satellite, files]) => files.forEach((file) => {
        payload.append('offline_files', file);
        payload.append('offline_satellites', satellite);
      }));
      localMoistureFiles.value.forEach((file) => payload.append('soil_moisture_files', file));
      if (measurementExcel.value) payload.append('measurement_excel', measurementExcel.value);
      requestConfig = { headers: { 'Content-Type': 'multipart/form-data' } };
    } else {
      payload = new FormData();
      payload.append('polygon', polygonResponse.data.id);
      payload.append('start_day', startDate.value);
      payload.append('end_day', endDate.value);
      payload.append('generation_mode', 'online');
      if (measurementExcel.value) payload.append('measurement_excel', measurementExcel.value);
      requestConfig = { headers: { 'Content-Type': 'multipart/form-data' } };
    }
    const resultResponse = await api.post('/api/result_img/', payload, requestConfig);
    jobId.value = resultResponse.data.id;
    jobProgress.value = Number(resultResponse.data.process || 0);
    jobStatus.value = resultResponse.data.status || 'Waiting';
    startProgressPolling();
    emit('api-status', true);
    feedbackType.value = 'success';
    feedback.value = `Processing job ${resultResponse.data.id} was created successfully.`;
  } catch (error) {
    emit('api-status', !error.request);
    feedbackType.value = 'error';
    const details = error.response?.data;
    if (error.response?.status === 409) {
      feedback.value = error.response.data?.detail || 'A task is already running. Please do not submit it again.';
      jobId.value = error.response.data?.id || null;
      jobProgress.value = Number(error.response.data?.process || 0);
      jobStatus.value = error.response.data?.status || 'Waiting';
      if (jobId.value) startProgressPolling();
    } else {
      feedback.value = typeof details === 'string' ? details : JSON.stringify(details || error.message);
    }
  } finally {
    submitting.value = false;
  }
}

async function rerunTest() {
  if (!testPreset.value || !jobId.value || rerunning.value) return;
  rerunning.value = true;
  feedback.value = '';
  jobError.value = '';
  try {
    const response = await api.post(`/api/result_img/${jobId.value}/rerun-test/`);
    jobProgress.value = Number(response.data.process || 0);
    jobStatus.value = response.data.status || 'Waiting';
    startProgressPolling();
    feedbackType.value = 'success';
    feedback.value = `Test project ${jobId.value} was restarted.`;
  } catch (error) {
    feedbackType.value = 'error';
    feedback.value = error.response?.data?.detail || `Unable to restart the test project: ${error.message}`;
  } finally {
    rerunning.value = false;
  }
}

function showCompletionNotice() {
  if (completionNoticeTimer) window.clearTimeout(completionNoticeTimer);
  completionNoticeVisible.value = true;
  completionNoticeProgress.value = 100;
  // Let the browser paint the full bar before shrinking it over three seconds.
  window.requestAnimationFrame(() => { completionNoticeProgress.value = 0; });
  completionNoticeTimer = window.setTimeout(() => {
    completionNoticeTimer = null;
    completionNoticeVisible.value = false;
  }, 3000);
}

function startNewProject() {
  window.location.reload();
}

function viewGeneratedResult() {
  if (!jobId.value) return;
  router.push({ path: '/', query: { result: String(jobId.value) } });
}

function stopProgressPolling() {
  if (progressTimer) window.clearInterval(progressTimer);
  progressTimer = null;
}

async function refreshProgress() {
  if (!jobId.value) return;
  try {
    const response = await api.get(`/api/result_img/${jobId.value}/progress/`);
    jobProgress.value = Math.max(0, Math.min(100, Number(response.data.process || 0)));
    const nextStatus = response.data.status || jobStatus.value;
    const wasCompleted = jobStatus.value === 'completed';
    jobStatus.value = nextStatus;
    if (response.data.error) jobError.value = formatJobError(response.data.error);
    if (jobStatus.value === 'completed' || jobStatus.value === 'failed') {
      stopProgressPolling();
      if (jobStatus.value === 'completed' && !wasCompleted) showCompletionNotice();
      if (jobStatus.value === 'failed') {
        feedbackType.value = 'error';
        feedback.value = jobError.value || 'Generation failed. Check the server log for details.';
      }
    }
  } catch {
    // Keep the last known progress; the next poll can recover from a transient error.
  }
}

function formatJobError(rawError) {
  const message = String(rawError || '').trim();
  if (!message) return '';
  if (/oauth2\.googleapis\.com|earth engine|ee\.initialize|connecttimeout|connection refused/i.test(message)) {
    return `Google Earth Engine could not be reached. Check network access and Earth Engine authentication. ${message}`;
  }
  return message;
}

function startProgressPolling() {
  stopProgressPolling();
  refreshProgress();
  progressTimer = window.setInterval(refreshProgress, 1000);
}

watch(mode, () => {
  // Switching to SHP is part of loading the offline test preset; preserve
  // its ready message instead of clearing it from the mode watcher.
  if (!testPreset.value) feedback.value = '';
});
watch([name, generationMode], () => {
  if (generationMode.value === 'offline' && name.value.toLowerCase() === 'test') loadTestPreset();
  else testPreset.value = null;
});
watch(name, (newName) => {
  if (uploadedPolygon.value && uploadedPolygon.value.name !== newName) {
    uploadedPolygon.value = null;
  }
});
onMounted(initializeMap);
onBeforeUnmount(() => {
  stopProgressPolling();
  if (completionNoticeTimer) window.clearTimeout(completionNoticeTimer);
  map?.destroy();
});
</script>

<style scoped>
.generation-workspace { position: relative; height: calc(100vh - 64px); min-height: 650px; display: grid; grid-template-columns: minmax(0, 1fr) 430px; background: #eef1ef; }
.boundary-map { position: relative; min-width: 0; background: #dfe5e1; }
.map-canvas { position: absolute; inset: 0; }
/* Match Explore's point-analysis affordance while drawing a boundary.  AMap
   applies its own cursor to the nested container/canvas, so force the
   crosshair through the map's complete child tree when Map clicks is active. */
.map-canvas.drawing-cursor,
.map-canvas.drawing-cursor :deep(.amap-container),
.map-canvas.drawing-cursor :deep(.amap-maps),
.map-canvas.drawing-cursor :deep(.amap-layers),
.map-canvas.drawing-cursor :deep(.amap-layer),
.map-canvas.drawing-cursor :deep(canvas) { cursor: crosshair !important; }
.completion-toast { position: absolute; z-index: 50; top: 16px; left: 50%; width: min(320px, calc(100% - 32px)); transform: translateX(-50%); padding: 10px 13px 9px; color: #285c3e; background: rgb(245 252 247 / 97%); border: 1px solid #a9cdb4; border-radius: 5px; box-shadow: 0 5px 20px rgb(23 32 29 / 20%); }
.completion-toast-title { display: flex; align-items: center; gap: 7px; font-size: 12px; font-weight: 700; }
.completion-toast-title i { color: #318254; }
.completion-toast-track { height: 3px; margin-top: 8px; overflow: hidden; background: #d7e8dc; border-radius: 99px; }
.completion-toast-track span { display: block; height: 100%; background: #4b9a69; transition: width 3s linear; }
.basemap-switch { position: absolute; z-index: 21; top: 20px; right: 20px; display: inline-flex; align-items: center; gap: 4px; padding: 4px; background: rgb(255 255 255 / 94%); border: 1px solid #d8dfdb; box-shadow: 0 3px 14px rgb(23 32 29 / 14%); }
.switch-label { padding: 0 6px; color: #607069; font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.switch-button { min-height: 30px; display: inline-flex; align-items: center; gap: 5px; padding: 0 8px; color: #46534d; background: transparent; border: 1px solid transparent; border-radius: 3px; font-size: 10px; font-weight: 650; }
.switch-button:hover { background: #edf3ef; }
.switch-button.active { color: #fff; background: #286443; border-color: #286443; }
.eyebrow { display: block; color: #607069; font-size: 10px; font-weight: 750; letter-spacing: .11em; }
.map-instruction { position: absolute; z-index: 20; top: 20px; left: 20px; padding: 13px 15px; background: rgb(255 255 255 / 94%); border-left: 3px solid #427256; box-shadow: 0 4px 18px rgb(23 32 29 / 14%); }
.map-instruction strong, .map-instruction small { display: block; }
.map-instruction strong { margin-top: 4px; font-size: 14px; }
.map-instruction small { margin-top: 4px; color: #68756f; font-size: 10px; }
.map-message { position: absolute; z-index: 22; top: 120px; left: 50%; transform: translateX(-50%); display: flex; gap: 8px; align-items: center; max-width: 480px; padding: 10px 13px; color: white; background: #17201d; box-shadow: 0 5px 20px rgb(0 0 0 / 20%); font-size: 11px; }
.map-tools { position: absolute; z-index: 20; right: 18px; bottom: 18px; display: flex; gap: 7px; }
.map-tools button { width: 38px; height: 38px; color: #304039; background: white; border: 1px solid #cbd4cf; border-radius: 4px; }
.generation-panel { overflow-y: auto; padding: 24px; background: #f9fbfa; border-left: 1px solid #d5ddd8; }
header { padding-bottom: 18px; border-bottom: 1px solid #dce2de; }
h1 { margin: 5px 0 8px; font-size: 22px; }
header p { margin: 0; color: #68756f; font-size: 12px; line-height: 1.55; }
form { padding-top: 18px; }
.field { margin-bottom: 15px; }
.field label, legend { display: block; margin-bottom: 6px; color: #46534d; font-size: 11px; font-weight: 700; }
.field input, .field textarea { width: 100%; padding: 9px 10px; color: #26332d; background: white; border: 1px solid #cad3ce; border-radius: 4px; outline: none; }
.field input { height: 38px; }
.field input[type="file"] { color: #52615a; font-size: 11px; }
.field input[type="file"]::file-selector-button { color: #385545; font-size: 11px; }
.field input.preset-date { color: #285c3e; background: #e7f3eb; border-color: #b8d7c1; }
.field textarea { resize: vertical; min-height: 120px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; line-height: 1.55; }
.field input:focus, .field textarea:focus { border-color: #5b866c; box-shadow: 0 0 0 2px rgb(91 134 108 / 12%); }
.field small { display: block; margin-top: 5px; color: #738079; font-size: 10px; }
fieldset { margin: 0 0 16px; padding: 0; border: 0; }
.segmented { display: grid; grid-template-columns: repeat(3, 1fr); padding: 3px; background: #e7ece9; border-radius: 5px; }
.segmented button { min-height: 34px; color: #5c6963; background: transparent; border: 0; border-radius: 3px; font-size: 11px; }
.segmented button.active { color: #244c35; background: white; box-shadow: 0 1px 4px rgb(23 32 29 / 12%); font-weight: 700; }
.date-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.offline-inputs { margin: -2px 0 12px; padding: 10px; background: #f4f7f5; border: 1px solid #d8e1db; }
.offline-inputs .field { margin-bottom: 8px; }
.offline-inputs small { display: block; color: #68756f; font-size: 10px; line-height: 1.4; }
.preset-path { min-height: 38px; display: flex; align-items: center; padding: 8px 10px; color: #285c3e; background: #e7f3eb; border: 1px solid #b8d7c1; border-radius: 4px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 10px; line-height: 1.35; overflow-wrap: anywhere; }
.preset-path.muted { color: #78847e; background: #f0f3f1; border-color: #d7dfda; font-family: inherit; }
.test-preset-hint { display: flex; align-items: center; gap: 7px; margin: -2px 0 14px; padding: 9px 10px; color: #286243; background: #e5f1e9; border-left: 3px solid #5a9b70; font-size: 11px; line-height: 1.4; }
.notice, .feedback { display: flex; align-items: flex-start; gap: 9px; margin: 2px 0 14px; padding: 10px; font-size: 10px; line-height: 1.45; }
.notice { color: #5c5538; background: #f5f0dd; border-left: 3px solid #b89c42; }
.feedback.error { color: #89382d; background: #fae9e5; border-left: 3px solid #d86651; }
.feedback.success { color: #286243; background: #e5f1e9; border-left: 3px solid #5a9b70; }
.job-progress { margin: 2px 0 14px; padding: 10px; background: #edf3ef; border-left: 3px solid #5a8668; }
.job-progress.failed { color: #89382d; background: #fae9e5; border-left-color: #d86651; }
.job-progress.completed { color: #286243; background: #e5f1e9; border-left-color: #5a9b70; }
.job-progress-head { display: flex; justify-content: space-between; gap: 12px; color: #33463b; font-size: 11px; font-weight: 700; }
.job-progress-head strong { color: #286443; }
.progress-track { height: 7px; margin: 8px 0 5px; overflow: hidden; background: #d5dfd8; border-radius: 99px; }
.progress-track span { display: block; height: 100%; background: #286443; border-radius: inherit; transition: width .35s ease; }
.job-progress small { display: block; color: #68756f; font-size: 10px; }
.job-progress .job-error { margin-top: 7px; color: #89382d; line-height: 1.45; white-space: normal; overflow-wrap: anywhere; }
.submit-button { width: 100%; min-height: 40px; display: flex; align-items: center; justify-content: center; gap: 8px; color: white; background: #286443; border: 1px solid #286443; border-radius: 4px; font-size: 12px; font-weight: 700; }
.submit-button:hover:not(:disabled) { background: #1f5136; }
.submit-button.completed { color: #68716c; background: #d6dbd8; border-color: #c2cac5; cursor: default; }
.test-rerun-button { width: 100%; min-height: 36px; display: flex; align-items: center; justify-content: center; gap: 7px; margin: 0 0 9px; color: #385545; background: #edf3ef; border: 1px solid #9caf9f; border-radius: 4px; font-size: 11px; font-weight: 650; }
.test-rerun-button:hover:not(:disabled) { background: #e1ece4; }
.completion-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 9px; }
.completion-actions button { min-height: 36px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; border-radius: 4px; font-size: 11px; font-weight: 650; cursor: pointer; }
.secondary-action { color: #385545; background: white; border: 1px solid #9caf9f; }
.secondary-action:hover { background: #edf3ef; }
.primary-action { color: white; background: #286443; border: 1px solid #286443; }
.primary-action:hover { background: #1f5136; }
button:disabled { cursor: not-allowed; opacity: .45; }
@media (max-width: 900px) {
  .generation-workspace { height: auto; min-height: calc(100vh - 58px); grid-template-columns: 1fr; }
  .boundary-map { height: 48vh; min-height: 360px; }
  .generation-panel { overflow: visible; border-left: 0; border-top: 1px solid #d5ddd8; }
}
@media (max-width: 520px) {
  .map-instruction { top: 64px; left: 12px; max-width: calc(100% - 24px); }
  .basemap-switch { top: 12px; right: 12px; }
  .switch-label { display: none; }
  .map-message { top: 150px; width: calc(100% - 24px); text-align: center; }
  .generation-panel { padding: 18px 16px; }
  .date-grid { grid-template-columns: 1fr; gap: 0; }
  .segmented { grid-template-columns: 1fr; }
}
</style>
