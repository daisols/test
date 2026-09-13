# FieldMoist Startup Guide

Language: English | [Chinese](STARTUP.zh-CN.md).

This is the short, routine startup reference. For a first installation, use the [First Installation Guide](First Installation Guide.md). It includes software installation, the complete data inventory, private-core placement and the first offline test.

## Prerequisites

- Windows 10/11 x64; the compiled core supports Python 3.12 x64 only
- Miniconda or Anaconda, with a `FieldMoist` environment created from `environment.yml`
- Node.js 22.12 or newer and npm
- The public application, matching private compiled core and supplied data in the locations described by the beginner manual
- Backend configuration in `public\.env` and frontend configuration in `public\frontend\.env`
- Database tables created with Django migrations
- An AMap JavaScript API key and security code if you want the basemap

The default display setup uses SQLite. MySQL is optional and should only be selected when an installation specifically requires it.

## 1. Start the Backend

Open an Anaconda Prompt and change to your actual public directory. The example path is `D:\FieldMoist\public`; use your own path if different:

```bat
cd /d D:\FieldMoist\public
conda activate FieldMoist
python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

Leave this window running. `--noreload` prevents the development server from restarting while a processing task is active.

## 2. Start the Frontend

Open a second Anaconda Prompt. Do not stop the backend window:

```bat
cd /d D:\FieldMoist\public
conda activate FieldMoist
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173/> in the browser. The backend health endpoint is <http://127.0.0.1:8000/api/health/>.

## Common Problems

- Missing data: run `python backend/manage.py validate_fieldmoist_data --dataset all` and restore the exact paths reported by the command.
- Core import failure: confirm Windows x64, Python 3.12 and the matching private package, then run `python tools/install_core.py --from-dir ..\private` followed by `python tools/smoke_native_core.py`.
- `npm.ps1` is blocked in PowerShell: reopen Anaconda Prompt, or use `npm.cmd` for the same command. The commands above use the CMD-style prompt.
- Blank AMap basemap: check `VITE_AMAP_KEY`, `VITE_AMAP_SECURITY_CODE`, allowed origins and network access, then restart the frontend.
- GDAL import failure: activate the supplied Conda environment and do not mix incompatible pip and Conda GDAL libraries.
- NASA POWER: cached grid responses are used first. Missing cells or dates require network access; local raster display does not.
- API or CORS error: check the health endpoint, `VITE_API_BASE_URL` and `CORS_ALLOWED_ORIGINS`, then restart both services after editing configuration.

## First Test and Network Notes

For a first local check, place the supplied data, run validation, migrations and `seed_fieldmoist` as described in the beginner manual. In the website, select **Offline**, enter lowercase `test`, wait for the preset to load and click **Start generation**. This bundled test uses local inputs and does not require GEE authentication.

Online mode requires an Earth Engine-enabled Google Cloud project. Set `EARTH_ENGINE_PROJECT` in `.env`, then run:

```bat
python tools/authorize_earth_engine.py
```

Authentication and satellite downloads need a network that can reach Google Earth Engine. This may not be possible from some networks in mainland China. AMap availability is separate from GEE availability.

## PNG Display and `test` Reruns

Colored PNG products are served locally and do not depend on AMap tiles or an `ImageLayer`. Existing products remain viewable when AMap is unavailable, and point-selection circles are drawn above the PNG.

Every offline `test` start removes that test's generated preprocessing copies, cycle caches, completion markers and old TIFF/PNG outputs, then recomputes from the original inputs. It keeps the supplied inputs, shared model and NASA cache. After a program update, restart the backend and frontend; do not delete the database or re-register project 83 for a routine update.
