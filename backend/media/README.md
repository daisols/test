# FieldMoist data directory

The daily products are not tracked by Git because the complete local dataset is approximately 85 GB. Place the data at this exact layout:

```text
backend/media/images/83/
├── shp/
│   ├── shp.shp
│   ├── shp.shx
│   ├── shp.dbf
│   └── shp.prj
└── 2018-05-01_2018-05-24/
    ├── soil_moisture_result/   # 24 YYYY-MM-DD.tif files
    ├── soil_moisture_png/      # 24 YYYY-MM-DD.png files
    └── nasa_power/              # cached NASA POWER grid responses
```

The simplified shapefile is the authoritative display and clipping boundary. Do not overwrite it. Daily GeoTIFF and PNG masks must remain aligned to this boundary. The visualization range is 0.00 to 0.40 m³/m³, using red → white → blue.

Extract `fieldmoist_test82_data.zip` and `fieldmoist_jiefangzha83_data.zip` into `backend/media`. They include NASA POWER responses respectively under each result-set's `nasa_power/` directory. Valid caches are reused by coordinate/date-range key; missing cells or dates still require network access.

Every test run clears generated products, preprocessing copies, cycle caches and completion markers before computing. Original inputs, the supplied shared model and NASA caches are retained. The refreshed 82 package contains only 37 input/cache files; it excludes previously generated rasters and cycle data.

The Amap base map is an online tile service. Amap tiles are not redistributed in this package; an Amap key and network connection are required for the satellite/standard background. The soil-moisture overlay, result navigation and offline `test` computation do not require GEE.

After placing the files, run `python backend/manage.py seed_fieldmoist`. The
command registers jiefangzha without deleting other research areas.

## Offline Test Inputs

The companion dataset must additionally contain:

```text
backend/media/images/82/
  shp/                           # .shp, .shx, .dbf, .prj
  offline/smap/                  # 24 dated SMAP_YYYY-MM-DD.tif inputs
  82/local_soil_moisture/         # soil_moisture_2018-05-11.tif and 2018-05-23
  82/measurements/measurements.xlsx
  2018-05-01_2018-05-24/process/shared_ml_model_rf.pkl
```
 Run`python backend/manage.py validate_fieldmoist_data --dataset all` before starting.

Data is provided separately and is not committed to either code repository.
Windows algorithm binaries are in the private core repository; use the public
application's `tools/install_core.py` to install them before starting the backend.
