# FieldMoist First Installation Guide

Language: English | [Chinese](首次安装指导.md). A printable [HTML edition](First Installation Guide.html) is included and can be opened by double-clicking it.

This manual describes the technical setup for Windows users without programming experience. It is reference documentation only. FieldMoist is displayed with all rights reserved; [LICENSE](LICENSE) grants no permission to run, copy, modify or redistribute the project. Receiving files or reading these instructions does not grant those rights.

The steps describe the matching `public` application, `private` Windows compiled core and separately supplied data. They first cover viewing **jiefangzha**, then running the local **test**, and finally optional online processing. Do not mix releases. Public code, private compiled files and data are separate deliveries; receiving one does not imply that the others are included.

## Contents

1. Before starting
2. Folders, filenames and command windows
3. Extract the public and private files
4. Install Miniconda and Node.js
5. Create the FieldMoist environment
6. Install the private compiled core
7. Data checklist and exact locations
8. Configure the backend and frontend
9. Check data and initialize the database
10. Install the frontend dependencies
11. Start both services and open the website
12. Check the jiefangzha display
13. Run the offline test
14. Shut down and start again later
15. Optional GEE authentication and online processing
16. Troubleshooting
17. First-installation checklist
18. Operation without an AMap basemap

## 1. Before Starting

### 1.1 Files to obtain from the project provider

| Item | Expected contents | Purpose |
| --- | --- | --- |
| Public application folder or ZIP | `backend`, `frontend`, `tools`, `environment.yml` | Website and backend application |
| Matching private folder or ZIP | `backend`, `LICENSE.txt`, `README.md` | Compiled algorithms required by the backend |
| `fieldmoist_jiefangzha83_data.zip` | Boundary, 24 TIFFs, 24 PNGs, NASA cache | Existing project 83 display |
| `fieldmoist_test82_data.zip` | Test boundary, 24 SMAP TIFFs, two moisture TIFFs, Excel measurements, shared model, NASA cache | Local project 82 calculation |
| `fieldmoist_online_data.zip`, optional initially | Models, mask and soil-property rasters | Processing raw satellite imagery |
| AMap browser credentials, optional | JavaScript API key and matching security code | Satellite and standard basemaps |

Code, compiled algorithms and data are separate deliveries. One does not imply the others are included. The private repository requires repository access arranged by the provider. Repository access is distinct from copyright permission.

Use the actual download links, external drive or shared folder supplied by the provider. This manual does not invent a data download address. Obtain missing files before continuing.

### 1.2 Computer requirements

1. Open Windows **Start**, then **Settings**.
2. Open **System**, then **About**.
3. Find **System type**. It must say a 64-bit operating system and an x64-based processor.
4. Windows ARM, 32-bit Windows, macOS and Linux cannot load these compiled files.

Use Windows 10 or 11, preferably at least 16 GB RAM. Reserve at least 40 GB on the project drive and approximately 10 GB on the system drive for installation. These are preparation recommendations for the examples, not guaranteed minimum requirements. Large research datasets need additional space.

Software installation and dependency downloads require internet access. After installation, local products and the supplied test can work without GEE. Missing NASA cache cells and online satellite downloads still require internet access. AMap is optional for the colored product display.

### 1.3 Example location used throughout this manual

```text
C:\FieldMoist\
    public\
    private\
```

Press **Win+E** to open File Explorer. Open **This PC**, then drive C:. Right-click an empty space, choose **New > Folder**, type `FieldMoist`, and press Enter.

If C: has insufficient space, use another local drive, such as `D:\FieldMoist`. Replace every example `C:\FieldMoist` path consistently. Avoid running inside a ZIP, USB drive, network share or automatically synchronized cloud folder. Copy the release to a local disk first.

## 2. Folders, Filenames and Command Windows

### 2.1 What a path means

`C:\FieldMoist\public\backend` means drive C:, then the FieldMoist folder, then public, then backend. You can paste a complete path into File Explorer's address bar and press Enter.

### 2.2 Show file extensions and hidden files

- Windows 11: choose **View > Show > File name extensions** and **Hidden items**.
- Windows 10: open the **View** tab and select **File name extensions** and **Hidden items**.

The suffix identifies the file type: `.py`, `.pyd`, `.tif`, `.png`, `.xlsx`. Configuration filenames must be exactly `.env`, not `.env.txt`.

### 2.3 Which command window to use

This manual uses **Anaconda Prompt**, available after installing Miniconda. Open Start, search for `Anaconda Prompt`, and click it. Commands labeled `bat` below are for this window. They also avoid PowerShell's `npm.ps1` policy issue.

Copy only the command inside a code block. Do not copy the surrounding explanation, the `(FieldMoist)` prompt, `C:\...>` or Markdown backticks. Paste one command, press Enter, and wait for it to finish before entering the next. Ordinary commands finish when the prompt returns. Servers are different: their windows stay occupied while they run.

This manual standardizes on Anaconda Prompt (CMD-style). If you use PowerShell, adapt `cd /d` and `copy` to that shell or reopen Anaconda Prompt; do not paste CMD commands into a Python `>>>` window.

## 3. Extract the Public and Private Files

### 3.1 Public application

1. Find the downloaded public ZIP in File Explorer.
2. Right-click it and choose **Extract All**.
3. Wait until extraction is finished.
4. Open the extracted folder until you can see `backend`, `frontend`, `tools` and `environment.yml` together.
5. Put those contents directly inside `C:\FieldMoist\public`.

The following files must exist:

```text
C:\FieldMoist\public\environment.yml
C:\FieldMoist\public\backend\manage.py
C:\FieldMoist\public\frontend\package.json
C:\FieldMoist\public\tools\install_core.py
```

An extra layer such as `public\public\backend` or `public\FieldMoist-main\backend` is incorrect. Move the contents of that extra inner folder up one level.

### 3.2 Private compiled files

Extract the matching private ZIP. Put the level containing `backend` and `LICENSE.txt` directly inside `C:\FieldMoist\private`.

```text
C:\FieldMoist\private\LICENSE.txt
C:\FieldMoist\private\backend\service\transform_tif\_native\win_amd64_cp312\manifest.json
```

The `win_amd64_cp312` directory contains `function1`, `function2`, `function3`, `predeal` and `manifest.json`. Each package contains `.pyd` files and an empty `__init__.py`.

Do not double-click a `.pyd`, rename it, change its extension to `.py`, or replace the public backend folder with the private backend folder. The installer copies only the required compiled files to the correct location.

## 4. Install Miniconda and Node.js

Skip installation if these tools already work, but check their versions. A separate system Python installation is unnecessary.

### 4.1 Miniconda

1. Visit <https://www.anaconda.com/docs/getting-started/miniconda/install>.
2. Download the Windows x64 installer, not ARM, Linux or macOS.
3. Double-click the installer.
4. Read its terms and decide whether to accept them.
5. **Just Me** and the default installation directory are generally sufficient.
6. Keep the recommended options; manually changing the system Python or PATH is unnecessary.
7. Finish the installation and open **Anaconda Prompt** from Start.
8. Run:

```bat
conda --version
```

A version number indicates that Conda is available. The base environment may use a different Python version; the dedicated project environment will use Python 3.12.

### 4.2 Node.js

1. Visit <https://nodejs.org/en/download>.
2. Select a Windows x64 `.msi` installer. Node.js 22 LTS, version 22.12 or newer, is recommended.
3. Run the installer and review its terms.
4. Keep npm selected. Extra native compiler tools are not required for this frontend.
5. Close and reopen Anaconda Prompt after installation.
6. Run these commands separately:

```bat
node --version
```

```bat
npm --version
```

Both must print versions. Do not type only `node`, which opens an interactive JavaScript prompt; press Ctrl+C twice if you enter it accidentally.

## 5. Create the FieldMoist Environment

### 5.1 Open the public application directory

In Anaconda Prompt:

```bat
cd /d C:\FieldMoist\public
```

`cd` changes directory; `/d` also changes drive if needed. Check that the environment file is present:

```bat
dir environment.yml
```

If the file is not found, correct the extraction layout before continuing.

### 5.2 Create and activate the environment

```bat
conda env create -f environment.yml
```

This downloads and installs dependencies and can take several minutes or longer. Keep the window open. Review any third-party terms or confirmation prompts before responding.

After creation finishes:

```bat
conda activate FieldMoist
```

The left side of the prompt must show `(FieldMoist)`. Verify:

```bat
python --version
```

```bat
python -c "import platform; print(platform.machine())"
```

Expected results are `Python 3.12.x` and `AMD64`. Do not continue with Python 3.13, 3.14, ARM or 32-bit Python. The compiled modules are specific to Windows x64 CPython 3.12.

`FieldMoist` is the new environment name. `SoilMoisturePlatform` is the maintainer's older environment and does not need to be created. If FieldMoist already exists, activate and check it instead of deleting it. Keep the environment activated for all Python commands; this also makes Conda's native libraries available.

## 6. Install the Private Compiled Core

Stay in `C:\FieldMoist\public` with `(FieldMoist)` active:

```bat
python tools/install_core.py --from-dir C:\FieldMoist\private
```

Expected success message:

```text
Windows core installed. Run python tools/smoke_native_core.py next.
```

`The matching core is already installed.` is also a successful result.

### 6.1 What the installer copies

| Source | Destination |
| --- | --- |
| `C:\FieldMoist\private\backend\service\transform_tif\_native\win_amd64_cp312` | `C:\FieldMoist\public\backend\service\transform_tif\_native\win_amd64_cp312` |
| `C:\FieldMoist\private\LICENSE.txt` | `C:\FieldMoist\public\backend\service\transform_tif\CORE_LICENSE.txt` |

There must be 26 `.pyd` modules in total, four empty package initializers and a manifest. Representative paths after installation are:

```text
backend\service\transform_tif\_native\win_amd64_cp312\function1\pipeline.cp312-win_amd64.pyd
backend\service\transform_tif\_native\win_amd64_cp312\function2\pipeline.cp312-win_amd64.pyd
backend\service\transform_tif\_native\win_amd64_cp312\function3\fusion_pipeline.cp312-win_amd64.pyd
backend\service\transform_tif\_native\win_amd64_cp312\predeal\pipeline.cp312-win_amd64.pyd
```

These are examples, not the complete module list. Do not edit `manifest.json`, which contains integrity hashes.

### 6.2 Check module loading

```bat
python tools/smoke_native_core.py
```

Expected final message:

```text
26 native imports and Windows worker checks passed.
```

If this fails, stop and check the private release version and Python architecture. Users do not need Cython or a compiler.

## 7. Data Checklist and Exact Locations

All supplied data belongs inside **`C:\FieldMoist\public\backend\media`**. Do not put it in `private`, the public root, or an extra nested `media` folder.

### 7.1 Extract the three data packages

| ZIP | Extract into | Required for |
| --- | --- | --- |
| `fieldmoist_jiefangzha83_data.zip` | `C:\FieldMoist\public\backend\media` | Existing jiefangzha display and cached point weather |
| `fieldmoist_test82_data.zip` | The same media folder | Local test calculation and cached point weather |
| `fieldmoist_online_data.zip` | The same media folder | Processing raw satellite inputs, including online projects |

Merge the directories already inside each ZIP directly into media. Do not add a folder named after the ZIP. The 82 package contains 37 original input, shared-model and NASA cache files; it excludes old results and cycle caches. Its compressed size is 9,638,255 bytes and extracted size is 257,205,058 bytes in the current delivery.

### 7.2 Project 83: existing display data

All table paths below are relative to `C:\FieldMoist\public\backend\media`.

| Files | Count | Relative location |
| --- | --- | --- |
| Shapefile components | Four required plus supplied `.cpg` | `images\83\shp\shp.shp`, `shp.shx`, `shp.dbf`, `shp.prj`, `shp.cpg` |
| Daily soil moisture TIFFs | 24 | `images\83\2018-05-01_2018-05-24\soil_moisture_result\2018-05-01.tif` through `2018-05-24.tif` |
| Daily display PNGs | 24 | `images\83\2018-05-01_2018-05-24\soil_moisture_png\2018-05-01.png` through `2018-05-24.png` |
| NASA cache responses | Five supplied JSON files | `images\83\2018-05-01_2018-05-24\nasa_power\` |

There is one TIFF and one PNG for each day from May 1 through May 24, 2018. Do not add `(1)`, `copy` or other text to filenames. Shapefile components must have the same base name and stay together; a `.shp` file alone is insufficient.

### 7.3 Project 82: test inputs

| Files | Count | Relative location |
| --- | --- | --- |
| Test boundary components | Four required plus supplied `.cpg` | `images\82\shp\shp.shp`, `shp.shx`, `shp.dbf`, `shp.prj`, `shp.cpg` |
| Daily SMAP TIFFs | 24 | `images\82\offline\smap\SMAP_2018-05-01.tif` through `SMAP_2018-05-24.tif` |
| Precomputed soil moisture | Two TIFFs | `images\82\82\local_soil_moisture\soil_moisture_2018-05-11.tif` and `soil_moisture_2018-05-23.tif` |
| Station measurements | One XLSX | `images\82\82\measurements\measurements.xlsx` |
| Shared model | One PKL | `images\82\2018-05-01_2018-05-24\process\shared_ml_model_rf.pkl` |
| NASA cache responses | Four supplied JSON files | `images\82\2018-05-01_2018-05-24\nasa_power\` |

The repeated **`82\82` is correct**. Do not remove either level. Project 83 and project 82 use different boundary folders. The test preset needs no manual Sentinel-1/Sentinel-2 uploads and no GEE authentication.

Keep the provided measurement workbook, including its `lon` and `lat` columns, unchanged. Do not convert it to CSV. The `.pkl` model is data, whereas `.pyd` files are compiled code; neither substitutes for the other. Use the matching model and input version, not a different model with the same name.

Do not add old `process\cycles`, `.stage1.complete`, `.stage2.complete`, `.fusion.complete` or generated test products to a fresh input delivery. Keep `shared_ml_model_rf.pkl`. Auxiliary files such as `.enp`, `.ebb`, `.ed1`, `.eq1` and `.qtr` are not required and do not replace TIFFs or shapefiles.

### 7.4 Check the complete layout

```text
C:\FieldMoist\public\backend\media\
  images\
    83\
      shp\                    (shp.shp, shp.shx, shp.dbf, shp.prj, shp.cpg)
      2018-05-01_2018-05-24\
        soil_moisture_result\ (24 dated TIFFs)
        soil_moisture_png\    (24 dated PNGs)
        nasa_power\           (five supplied JSON responses)
    82\
      shp\                    (shp.shp, shp.shx, shp.dbf, shp.prj, shp.cpg)
      offline\smap\           (24 SMAP_YYYY-MM-DD.tif files)
      82\
        local_soil_moisture\  (the May 11 and May 23 TIFFs)
        measurements\measurements.xlsx
      2018-05-01_2018-05-24\
        process\shared_ml_model_rf.pkl
        nasa_power\           (four supplied JSON responses)
```

Parenthesized text explains the contents; do not create files with those names.

If a provider's outer folder is `media`, copy its contents into the target media folder. If the outer folder is `images`, put that folder in media. If only `82` and `83` are present, put them inside `media\images`.

Correct example:

```text
C:\FieldMoist\public\backend\media\images\83\shp\shp.shp
```

Incorrect examples:

```text
C:\FieldMoist\public\backend\media\media\images\83\shp\shp.shp
C:\FieldMoist\public\images\83\shp\shp.shp
C:\FieldMoist\private\backend\media\images\83\shp\shp.shp
```

The [per-file inventory](DATA_INVENTORY.csv) lists names, target paths and baseline sizes. It contains 95 files, including both `.cpg` files and nine NASA responses, totaling 3,250,551,078 bytes (about 3.03 GiB). This excludes installed software, intermediate calculations and new results. Do not reserve only 3 GB.

If Windows asks to replace files, confirm that you are not overwriting an existing project's data. A first installation should use a fresh directory.

### 7.5 Additional data for raw satellite processing

The online package supplies these paths relative to media:

| File | Relative path |
| --- | --- |
| LAI model | `model\model_LAI.pkl` |
| ALA model | `model\model_ALA.pkl` |
| CWC model | `model\model_CWC.pkl` |
| AIEM-Dobson model | `model\AIEM_Dobson.pkl` |
| Coarse reference raster | `mask_tif\coarse.tif` |
| Clay raster | `Clay_Sand_RongZhong_tifs\Clay.tif` |
| Sand raster | `Clay_Sand_RongZhong_tifs\Sand.tif` |
| Bulk density raster | `Clay_Sand_RongZhong_tifs\RongZhong.tif` |

These files are not needed for the bundled direct-moisture test. They are needed when processing raw satellite imagery. Coverage, CRS and model version must match the intended calculation. Never create an empty placeholder to silence a missing-file error. GEE authentication does not download these local models automatically.

## 8. Configure the Backend and Frontend

### 8.1 Create the two configuration files once

In `C:\FieldMoist\public`, run separately:

```bat
copy .env.example .env
```

```bat
copy frontend\.env.example frontend\.env
```

If asked to overwrite an existing file, answer **N** until you have checked and backed up your existing configuration.

- `C:\FieldMoist\public\.env` configures the backend.
- `C:\FieldMoist\public\frontend\.env` configures the frontend.

### 8.2 Backend settings

```bat
notepad .env
```

For local operation, retain:

```ini
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
DB_ENGINE=sqlite
```

SQLite creates its own database file and requires no MySQL server or password. Generate a backend secret in the activated prompt:

```bat
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the printed random string into `.env` after `DJANGO_SECRET_KEY=`. Keep the key name and equals sign. Do not copy the command prompt itself. Press Ctrl+S and close Notepad.

For the first offline test, leave GEE settings empty and retain the default media location and processing mode. Do not remove comment markers from `FIELD_MOIST_MEDIA_ROOT` or `FIELDMOIST_G_*` unless intentionally configuring those options.

### 8.3 Frontend settings

```bat
notepad frontend\.env
```

Use this API address for the local backend:

```ini
VITE_API_BASE_URL=http://127.0.0.1:8000/
```

For an optional basemap, enter the actual provider-issued values for `VITE_AMAP_KEY` and `VITE_AMAP_SECURITY_CODE`. Obtain a **Web / JavaScript API** key, not a Web Service or mobile-app key, from <https://lbs.amap.com/>. Restrict it to the local hostnames/origins required by AMap, including localhost and 127.0.0.1 where applicable.

Without valid AMap credentials, local colored PNGs and point selection can still work, but the satellite/standard background will be absent. Save the file using Ctrl+S and confirm it is named `.env`, not `.env.txt`. Restart the relevant service after editing its configuration.

## 9. Check Data and Initialize the Database

### 9.1 Validate the data files

Keep `(FieldMoist)` active in the public directory. Run each command separately:

```bat
python backend/manage.py validate_fieldmoist_data --dataset all
```

Expected: `all dataset validation passed.` If files are missing or invalid, fix the exact reported paths before continuing.

### 9.2 Create the database tables

```bat
python backend/manage.py migrate
```

Migration creates the database tables. A new database prints multiple `Applying ... OK` lines. Later it can print `No migrations to apply`.

### 9.3 Register the jiefangzha display data

```bat
python backend/manage.py seed_fieldmoist
```

**Do not skip seed_fieldmoist.** Migration creates tables; the seed command registers the jiefangzha display project from the supplied files. Without registration, Explore may report no matching polygon despite a successful environment and data check. The command does not delete other study areas.

### 9.4 Check the backend configuration

```bat
python backend/manage.py check
```

Expected: `System check identified no issues`. Do not copy the maintainer's old database into a fresh installation. You do not need a Django administrator account for these example workflows.

## 10. Install the Frontend Dependencies

From the public directory:

```bat
npm ci --prefix frontend
```

Then:

```bat
npm run build --prefix frontend
```

The first command downloads the locked JavaScript dependencies. The second checks the production build. A Vite message about chunks larger than 500 kB is a warning; a final successful `built` message means the build completed. `vite` not found usually means npm installation did not finish in this project directory.

Do not automatically run `npm audit fix --force`, which can change dependency versions.

## 11. Start Both Services and Open the Website

### 11.1 Window A: backend

Open Anaconda Prompt and run:

```bat
cd /d C:\FieldMoist\public
conda activate FieldMoist
python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

The backend should print `Starting development server at http://127.0.0.1:8000/`. Leave this window open. It is normal that the prompt does not return.

### 11.2 Window B: frontend

Open a second Anaconda Prompt. Do not type frontend commands into the running backend window.

```bat
cd /d C:\FieldMoist\public
conda activate FieldMoist
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

Leave this window open too. Its local address should use port 5173. If that port is occupied, stop the older known frontend process or have the provider configure another matching frontend port and CORS setting; do not silently use a different port.

### 11.3 Open the website

Open your browser and type <http://127.0.0.1:5173/> in the address bar. Use `http`, not `https`. Do not double-click `frontend\index.html` to run the application.

Check <http://127.0.0.1:8000/api/health/> in another tab. A successful response with status `ok` confirms that the API is reachable. A backend root URL without an application page is not itself an error; use the frontend URL for the website.

## 12. Check the Jiefangzha Display

Explore should show:

- Project name **jiefangzha**, dataset ID 83 and 24 daily products.
- An initial date of 2018-05-01 and a colored soil moisture PNG.
- A color scale from 0.00 to 0.40 m3/m3.
- Working previous/next-date controls and GeoTIFF download.

AMap may show a satellite or standard basemap when credentials and connectivity are available. `Basemap unavailable` does not mean the local soil moisture product should disappear.

Enable **Point analysis**, then click inside the colored region. The circle should appear above the image. For covered points and dates, NASA data loads from the local cache. A request outside the supplied cache coverage still needs internet access. Changing dates retains the selected point; switching projects clears it.

If there is no matching polygon, verify that `seed_fieldmoist` ran successfully against the same backend database and media directory used by the running server.

## 13. Run the Offline Test

### 13.1 Load and run the preset

1. Keep both service windows open.
2. Select **Generate** in the top navigation.
3. Select **Offline** under **Processing mode**.
4. Enter lowercase `test` in **Area name**, without quotes or spaces.
5. Click outside the input and wait for the preset to load.
6. Confirm the boundary and dates were filled automatically: 2018-05-01 through 2018-05-24.
7. When `Offline test dataset is ready. Click Start generation.` appears, click **Start generation**.
8. Wait for **Completed** and 100 percent.
9. Click **View generated result** to inspect the result in Explore.

Do not upload additional SMAP, Sentinel, boundary or measurement files for the preset. Do not change its dates or change project 82 to 83.

### 13.2 Normal behavior while calculating

The backend prints at most a short message for each major stage: loading data, preprocessing imagery, computing moisture, generating colored products and completion. Per-file progress bars and internal computation details are hidden. A quiet window is normal and does not mean processing stopped.

CPU and memory use may rise. The website progress advances by stages, not necessarily every second. Recent test runs on the maintainer's computer took about two minutes; slower computers can take longer.

Do not let the computer sleep, close the backend or submit another test during computation. Wait while the task remains active.

### 13.3 Result locations

```text
C:\FieldMoist\public\backend\media\images\82\2018-05-01_2018-05-24\soil_moisture_result\
C:\FieldMoist\public\backend\media\images\82\2018-05-01_2018-05-24\soil_moisture_png\
```

The first directory should contain 24 dated TIFFs; the second should contain 24 matching PNGs. Intermediate files appear under `process`; do not move them while the task runs.

`ml_patch_report.xlsx` is **not generated by default**. The station measurement workbook is still required as input. Absence of an output report does not mean the station correction step was skipped.

These paths describe the supplied fresh setup. A database imported from another installation can have different records; do not manually renumber database entries.

### 13.4 Rerun or update

Use **Run test again** for another run. Every test start, including retries, removes generated preprocessing copies, cycle caches, completion markers and old test TIFF/PNG outputs, then recomputes from original inputs. It preserves SMAP inputs, supplied moisture TIFFs, Excel, SHP, the shared model and NASA caches. Copy previous results outside the project before rerunning if you need to retain them. Other projects keep their existing resume behavior.

For a release update, stop the backend, update matching public and private program files, retain your data and `.env` files, and run from public:

```bat
conda activate FieldMoist
python tools/install_core.py --from-dir ..\private --upgrade
python tools/smoke_native_core.py
npm run build --prefix frontend
```

Restart both services and refresh the browser. Do not delete the database, the `images\82` folder or the shared model to reset the test. A routine program update does not require repeating `seed_fieldmoist`.

## 14. Shut Down and Start Again Later

### 14.1 Shut down normally

Wait until calculation finishes. In each service window, press **Ctrl+C**; confirm termination if Windows asks. You can then close the windows and browser.

### 14.2 Start again on a later day

On subsequent days, repeat only the two service-start sequences from section 11. Keep the same project directory and activate FieldMoist in each new Python command window. Do not recreate the environment, overwrite `.env`, reinstall all dependencies, re-extract all data or reset the database every day.

Closing the browser alone does not stop backend calculations. Do not power off while files are being written.

### 14.3 What to back up

When no task is running and the backend is stopped, back up your own `backend\db.sqlite3`, `backend\media` and local configuration files. Store backups outside the project and do not upload them to the public repository.

Restore the database together with the matching media directory; do not replace one without the other. Back up before updating the public code or compiled core. Ask the provider to confirm the matching directory when changing core versions.

## 15. Optional GEE Authentication and Online Processing

### 15.1 What Online mode additionally requires

Online processing requires an Earth Engine-enabled Google Cloud project, an account with access to it, a network that can reach GEE and the ancillary files listed in section 7.5. Obtain the actual project identifier; do not use an email address or display name.

### 15.2 Enter your GEE project ID

In the activated FieldMoist prompt, from public, edit the backend `.env` and replace the value after `EARTH_ENGINE_PROJECT=` with your project ID. Save the file and restart the backend after configuration changes.

### 15.3 Complete first-time Earth Engine authentication

Run:

```bat
python tools/authorize_earth_engine.py
```

This is the supported equivalent of the original `polygon_save/authorize.py` authentication script. Follow the browser and terminal instructions, choose the correct account and complete Google's authorization steps. Authentication screens may change. Do not disclose verification codes, full authorization URLs or credentials.

**Please pay attention to your network environment. GEE may be unreachable from networks in mainland China.** Authentication and satellite downloads require a connection that can reach Google Earth Engine. This is separate from AMap availability. The local `test` requires neither GEE authentication nor a GEE connection.

### 15.4 Prepare inputs and select the area

For service-account deployments, the configuration also supports a service-account email and JSON credential path. Beginners should have the provider configure these; keep credentials outside version control. Extract the online ancillary data listed in section 7.5. In Generate, choose **Online**, enter a region name and valid dates, then define the area:

- **SHP file**: upload a ZIP containing matching `.shp`, `.shx`, `.dbf` and `.prj` files, or select the components together. The `.prj` is required to transform the boundary to WGS84.
- **Coordinates**: enter the required WGS84 coordinate pairs in longitude, latitude order using the page's coordinate input.

Both ways of defining the area work without a basemap. Online mode still needs GEE to fetch images; it does not become disconnected operation merely because the map background is hidden.

For a custom **Offline** job, define the area by SHP or WGS84 coordinates and supply the local input files requested by the selected processing path. Files must cover the area and dates. The bundled `test` remains the simplest first validation because its inputs already match.

## 16. Troubleshooting

### 16.1 Conda is not recognized

Open **Anaconda Prompt** from Start. A normal command window may not have Conda configured. If it is missing from Start, check the Miniconda installation.

### 16.2 Wrong working directory

Run `cd /d C:\FieldMoist\public`, then `dir environment.yml`. Correct extra extraction layers if the file is missing. PowerShell uses `cd` without `/d`.

### 16.3 Python or architecture mismatch

Activate FieldMoist and check Python 3.12 and AMD64. A `.pyd` compiled for one Python minor version or architecture cannot be fixed by renaming it.

### 16.4 Django is missing

If the prompt shows `(base)`, run `conda activate FieldMoist` in that window. Each new window needs activation. Do not install Django into base to work around this.

### 16.5 Private core missing or different

Check the `--from-dir` path and private `manifest.json`. Run the installer before algorithm-dependent backend commands. For a different release, update the public code too, stop the backend and use `--upgrade`. Do not edit hashes or rename binaries.

### 16.6 A core file is in use

Stop the backend and any known processing workers before upgrading. Loaded Windows `.pyd` files can be locked. Do not terminate unrelated programs indiscriminately.

### 16.7 GDAL or NumPy native-library errors

Use the supplied Conda environment and activate it. Avoid mixing pip GDAL with incompatible Conda libraries. Launching a Python executable directly without activation can omit required DLL paths. Report the environment details before replacing packages.

### 16.8 Data validation fails

Read the exact missing or invalid path. Check the project ID, repeated `82\82`, dates, extensions and archive nesting. Never create empty files as replacements.

### 16.9 No matching polygon in Explore

After placing data and running migrations, run `python backend/manage.py seed_fieldmoist`. Confirm the running backend uses the same database and media directory. Do not delete the database as a first response.

### 16.10 npm or Vite is missing

Reopen the command window after installing Node.js. Check `node --version` and `npm --version`. Run `npm ci --prefix frontend` from public before building or starting Vite. In PowerShell, `npm.cmd` can avoid a blocked `npm.ps1` script.

### 16.11 Build warns about large chunks

A warning followed by successful `built` output does not mean failure. Do not change dependency versions solely to remove this message.

### 16.12 Website does not open

Keep both service windows running. Use <http://127.0.0.1:5173/>, not HTTPS or a directly opened HTML source file. Check whether another process already occupies a required port.

### 16.13 API unavailable or CORS error

Open <http://127.0.0.1:8000/api/health/>. If it fails, inspect the backend window. If it succeeds, check `VITE_API_BASE_URL` and backend `CORS_ALLOWED_ORIGINS`. Restart both services after changing configuration.

### 16.14 Blank basemap or missing PNG

For the background, check AMap credentials, allowed origins and connectivity. For a missing colored product, check local data, registration and the selected result. Existing jiefangzha products do not require GEE. A blank basemap and a missing product are different failures.

### 16.15 Test preset does not fill in

Select Offline first, enter exactly `test`, click outside and wait. Check the page error, backend availability, installed core and complete project 82 inputs.

### 16.16 Start button is unavailable or progress is quiet

Wait for the preset to finish loading and verify dates and active tasks. A completed test has a separate **Run test again** command. During a calculation, a quiet backend window is normal; it prints only stage summaries. Do not submit duplicate tasks.

### 16.17 Excel or model compatibility error

Keep the provider's workbook format and matching shared model. Supply the code/core version, model filename and error message to the provider. Do not substitute a similarly named file.

### 16.18 NASA request fails while offline

Only cached grid cells and date ranges are available offline. Existing cache responses are reused; missing coverage needs a network connection. Local raster display and the bundled test do not require a successful NASA download.

### 16.19 Asking for help

Report the manual section, exact command, Python version, task ID, data directory and the last 20-30 relevant error lines. Keep enough context to identify the failure. Do not send `.env` contents, map keys, passwords, Google codes or full authentication URLs. A filename list is usually enough to diagnose missing data initially.

## 17. First-Installation Checklist

- [ ] Windows x64 and sufficient disk space confirmed.
- [ ] Public directly contains environment.yml, backend, frontend and tools.
- [ ] Private directly contains LICENSE.txt and backend.
- [ ] Conda, Node.js and npm version checks succeed.
- [ ] FieldMoist is active, with Python 3.12 and AMD64.
- [ ] The core installer and 26-module smoke check succeed.
- [ ] Project 83 boundary, 24 TIFFs, 24 PNGs and NASA cache are in place.
- [ ] Project 82 boundary, 24 SMAP TIFFs, two moisture TIFFs, Excel, shared model and NASA cache are in place.
- [ ] Repeated 82/82 directories are correct; no stale test results were added to fresh inputs.
- [ ] Both .env files exist with correct local API settings and no accidental .txt suffix.
- [ ] Data validation, migrations, seed_fieldmoist and Django checks succeed.
- [ ] npm installation and build succeed.
- [ ] Both services run and API health is reachable.
- [ ] Explore displays jiefangzha and 24 daily colored products.
- [ ] The Offline test preset completes at 100 percent.
- [ ] Test output contains 24 TIFFs and 24 PNGs, with no required output report workbook.
- [ ] Subsequent startup needs only the two service windows.

Online authentication and downloading are separate from these local example checks.

## 18. Operation Without an AMap Basemap

Explore renders product PNGs independently of AMap. If the SDK does not load or its tiles are unavailable, local products, project/date navigation and point selection still work. The selected circle is above the colored PNG. Keep the local frontend and backend running even when disconnected from the internet.

The project does not bundle AMap tiles. Previously cached tiles may display, but uncached tiles and zoom levels are not guaranteed. SHP upload and WGS84 coordinate entry do not depend on a basemap in either processing mode.

The release data packages are extracted into `public/backend/media`: `fieldmoist_test82_data.zip` contains project 82 inputs and NASA files, `fieldmoist_jiefangzha83_data.zip` contains project 83 display data and NASA cache, and `fieldmoist_online_data.zip` contains the optional online-processing files. Merge the package contents directly into media; do not add another folder named after the ZIP. Existing valid cache cells and date ranges are reused without downloading. Missing coverage needs internet. Online processing still requires GEE access and ancillary data. Already complete local inputs do not need to be extracted again for a routine code update.
