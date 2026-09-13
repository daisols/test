# FieldMoist

启动说明：[中文](STARTUP.zh-CN.md) | [English](STARTUP.md)  
首次安装指导：[中文](首次安装指导.md) | [English](First Installation Guide.md)  
可打印 HTML：[中文](首次安装指导.html) | [English](First Installation Guide.html)  
English README：[README.md](README.md)

这些文件仅作技术参考。FieldMoist 当前发布版本只用于展示；权利说明见 [LICENSE](LICENSE)。

## 项目用途

FieldMoist 是一个可生成逐日农田土壤水分的网页系统。本次发布提供的展示区是 **jiefangzha**（多边形 83），包含 2018-05-01 至 2018-05-24 的 24 天产品；另有项目 82 的离线 `test` 测试流程，可供复现**jiefangzha**（多边形 83）。

网页支持逐日地图浏览、点位土壤水分与 NASA POWER 时间序列、GeoTIFF 下载，以及可选的高德卫星/标准底图。已有本地 PNG 和离线 test 不依赖 GEE，也不要求高德底图一定可用。

## 环境与组成

- Windows 10/11 x64，Python 3.12 x64
- Miniconda 或 Anaconda，使用项目提供的 `environment.yml`
- Node.js 22.12 或更高版本，以及 npm
- 公开程序代码和获得授权、版本匹配的私有编译核心
- 解压并放置到 `backend/media` 下的配套数据包
- 用于底图的高德 JavaScript API Key 和安全密钥（可选）
- 用于 Online 在线处理的 Google Earth Engine 项目和认证（可选）

后端采用 Django 和 Django REST Framework；前端基于 Vue 3 和 Vite 构建，集成 Tailwind CSS，并使用 ECharts 进行数据可视化。GDAL、Rasterio、GeoPandas 等地理空间库负责栅格与矢量数据处理，NumPy、pandas、SciPy 和 scikit-learn 等科学计算库提供数据分析与模型计算支持。项目为轻量化展示使用SQLite 数据库，支持切换到 MySQL。

## 快速开始

第一次安装请阅读[首次安装指导](首次安装指导.md)。手册说明公开/私有文件和数据的取得方式、私有算法安装、`.env` 配置、数据检查、数据库初始化、前后端启动和离线 test 操作。

在 `public` 目录中，核心命令如下：

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

在两个 Anaconda Prompt 窗口中分别启动后端和前端：

```bat
python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

```bat
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

然后打开 <http://127.0.0.1:5173/>，选择 **Offline**，输入小写 `test`，等待预设加载后点击 **Start generation**。本地测试不上传 Sentinel 数据，也不需要 GEE 认证。

## 数据与权利

栅格、边界、模型和缓存文件与源代码分开提供。需要的目录结构和文件数量见首次安装指导的数据清单；如果配套目录存在，也可查看 [backend/media/README.md](backend/media/README.md)。不要用同名文件替代、创建空占位文件，或混用项目 82 与项目 83 的目录。

公开代码和私有编译核心是两份不同交付物。获得其中一份不代表获得另一份的使用权。使用或另行分发影像、模型和派生产品前，请确认你拥有相应权限。项目和编译核心均保留所有权利，技术说明不构成许可。

## 目录结构

```text
FieldMoist/
├── backend/                    Django API 与处理流程
├── frontend/                  Vue/Vite 网页应用
├── tools/                     数据检查、核心安装和 smoke 检查
├── environment.yml            推荐的 Conda 环境
├── STARTUP.md                 简明启动说明（英文）
├── STARTUP.zh-CN.md           简明启动说明（中文）
├── 首次安装指导.md       首次安装指导（中文）
├── First Installation Guide.md          首次安装指导（英文）
├── 首次安装指导.html     可打印首次安装指导（中文）
├── First Installation Guide.html        可打印首次安装指导（英文）
├── README.md                  英文项目说明
└── README.zh-CN.md            中文项目说明
```

## 在线处理

Online 在线模式需要启用 Earth Engine 的 Google Cloud 项目。在后端 `.env` 填写 `EARTH_ENGINE_PROJECT`，再运行 `python tools/authorize_earth_engine.py`。GEE 认证和卫星下载需要能够访问 Google Earth Engine 的网络，这与高德底图是否可用无关。NASA POWER 会优先使用本地缓存，未覆盖的网格或日期才需要联网。

## 引用与求助

引用项目时请使用 [CITATION.cff](CITATION.cff) 中的元数据。有问题时请查阅手册章节，检查完整命令、Python 版本、任务 ID 和相关错误行。
