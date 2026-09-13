# FieldMoist

Startup: [English](STARTUP.md) | [Chinese](STARTUP.zh-CN.md)  
First Installation Guide: [English](First Installation Guide.md) | [Chinese](首次安装指导.md)  
Printable HTML: [English](First Installation Guide.html) | [Chinese](首次安装指导.html)  
Chinese README: [README.zh-CN.md](README.zh-CN.md)

These files are technical reference documentation. FieldMoist is a display-only release; see [LICENSE](LICENSE) for the rights notice.

## Project Purpose

FieldMoist is a web system for generating daily farmland soil-moisture products. This release provides the **jiefangzha** display area (polygon 83), with 24 daily products from 2018-05-01 through 2018-05-24. It also includes an offline `test` workflow for project 82 that can reproduce **jiefangzha** (polygon 83).

The website supports daily map browsing, point-based soil-moisture and NASA POWER time series, GeoTIFF downloads, and optional AMap satellite or standard basemaps. Existing local PNG products and the offline test do not depend on GEE or require the AMap basemap to be available.

## Environment and Components

- Windows 10/11 x64 with Python 3.12 x64
- Miniconda or Anaconda, using the supplied `environment.yml`
- Node.js 22.12 or newer and npm
- Public application code plus an authorized, version-matched private compiled core
- Companion data packages extracted under `backend/media`
- Optional AMap JavaScript API key and security code for the basemap
- Optional Google Earth Engine project and authentication for Online processing

The backend uses Django and Django REST Framework. The frontend is built with Vue 3 and Vite, integrates Tailwind CSS, and uses ECharts for visualization. GDAL, Rasterio, GeoPandas and related geospatial libraries process raster and vector data; NumPy, pandas, SciPy and scikit-learn provide scientific analysis and model computation. SQLite is used for lightweight display and can be switched to MySQL when necessary.

## Quick Start

For a first installation, read the [First Installation Guide](首次安装指导.md). It explains how to obtain the public/private files and data, install the private algorithm, configure `.env`, validate data, initialize the database, start the backend and frontend, and run the offline `test`.

From the `public` directory, run the core commands:

```bat
conda env create -f environment.yml
conda activate FieldMoist
python tools/install_core.py --from-dir ..\private
python tools/smoke_native_core.py
copy .env.example .env
copy frontend\.env.example frontend\.env
python backend/manage.py validate_fieldmoist_data --dataset all
python backend/manage.py migrate
python backend/manage.py seed_fieldmoist
python backend/manage.py check
npm ci --prefix frontend
npm run build --prefix frontend
```

Start the backend and frontend in two separate Anaconda Prompt windows:

```bat
python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

```bat
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173/>, select **Offline**, enter lowercase `test`, wait for the preset to load, and click **Start generation**. The local test does not upload Sentinel data and does not require GEE authentication.

## Data and Rights

Raster, boundary, model and cache files are supplied separately from the source. The required directory layout and file counts are listed in the First Installation Guide; if the companion directory is present, see [backend/media/README.md](backend/media/README.md). Do not substitute same-named files, create empty placeholders, or mix project 82 and project 83 directories.

The public application and private compiled core are separate deliveries. Receiving one does not grant access or rights to the other. Confirm that you have permission to use or redistribute imagery, models and derived products. The project and compiled core reserve all rights; technical instructions do not constitute a license.

## Repository Layout

```text
FieldMoist/
├── backend/                    Django API and processing pipeline
├── frontend/                   Vue/Vite web application
├── tools/                      validation, core installation and smoke checks
├── environment.yml             recommended Conda environment
├── STARTUP.md                  short startup guide (English)
├── STARTUP.zh-CN.md            short startup guide (Chinese)
├── 首次安装指导.md         First Installation Guide (Chinese)
├── First Installation Guide.md           First Installation Guide (English)
├── 首次安装指导.html       printable First Installation Guide (Chinese)
├── First Installation Guide.html         printable First Installation Guide (English)
├── README.md                   English project overview
└── README.zh-CN.md             Chinese project overview
```

## Online Processing

Online mode requires an Earth Engine-enabled Google Cloud project. Set `EARTH_ENGINE_PROJECT` in the backend `.env`, then run `python tools/authorize_earth_engine.py`. GEE authentication and satellite downloads require a network that can reach Google Earth Engine; this is separate from AMap availability. NASA POWER uses local caches first and only needs network access for uncovered cells or dates.

## Citation and Support

Use the metadata in [CITATION.cff](CITATION.cff) when citing the project. For questions, consult the First Installation Guide and provide the exact command, Python version, task ID and relevant error lines. Do not send `.env` contents, map keys, passwords, Google verification codes or full authorization URLs.
