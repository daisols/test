# FieldMoist 启动说明

语言：中文 | [English](STARTUP.md)。

本文档仅做常规启动说明。第一次安装调试，请使用 [首次安装指导](首次安装指导.md)，查看详细步骤，其中包含软件安装、完整数据清单、私有算法安装位置和逐步操作。

## 环境要求

- Windows 10/11 x64 与 PowerShell；编译算法仅支持 Python 3.12 x64
- Miniconda 或 Anaconda
- Node.js 22.12 或更高版本，以及 npm
- 已按environment.yml文件构建虚拟环境
- 已检查 FieldMoist 运行相关数据和完整代码
-  配置好后端配置
- 配置好用于底图的高德地图 JavaScript API Key 和安全密钥
- 已初始化数据库，创建数据库表
- 
- 系统创建时使用MySQL，为方便展示使用轻量化 SQLite。只有 MySQL必要时才进行切换。

## 1. 启动后端

打开项目根目录（不一定是D:\FieldMoist\public，视实际情况而定）：

```powershell
cd /d D:\FieldMoist\public
```

在项目根目录打开虚拟环境：

```powershell
conda activate FieldMoist
```
建议使用 Conda，因为 GDAL 和 Rasterio 的本地动态库版本必须匹配。

启动后端：

```powershell
python backend/manage.py runserver 127.0.0.1:8000 --noreload
```

## 2. 启动前端

独立于后端，新开一个窗口

打开项目根目录（不一定是D:\FieldMoist\public，视实际情况而定）：

```powershell
cd /d D:\FieldMoist\public
```

在项目根目录打开虚拟环境：

```powershell
conda activate FieldMoist
```

启动前端：

```powershell
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173 --strictPort
```

本机浏览器访问 `http://127.0.0.1:5173`

## 常见问题

- 数据文件缺失：运行 `python backend/manage.py validate_fieldmoist_data --dataset all`，按报告补齐输入。
-  Explore 页面默认使用的高德地图的卫星底图，可通过地图右上角的 Satellite / Standard 开关自由切换卫星底图还是标准底图。
- 核心模块加载失败：确认使用 Windows x64 和 Python 3.12，使用 `tools/install_core.py` 安装匹配版本的私有编译文件。
- PowerShell 提示不能加载 `npm.ps1`：执行 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 后重开 PowerShell，或使用 `npm.cmd`。
- 底图空白：检查两个高德环境变量及域名白名单，修改后重启 Vite。
- 高德底图瓦片首次使用后会保存到浏览器的 `FieldMoist AMap tiles` 缓存。在 `localhost` 或 HTTPS 下由内置 Service Worker 管理；通过不安全的局域网 HTTP 地址访问时，浏览器可能只使用普通 HTTP 缓存，这是浏览器对 Service Worker 的安全限制。
- GDAL 导入失败：重新创建 Conda 环境，避免混用不同来源的 GDAL 动态库。
- NASA POWER 优先读取已缓存的网格数据，只有缓存缺失时才需要网络；本地逐日影像浏览不受影响。高德不可用时仍可显示土壤水分产品，只是不显示底图。
- 如需离线查看底图，请在联网时打开目标区域，分别切换 Satellite 和 Standard，并浏览需要的区域与缩放级别。离线只能显示已经浏览过的瓦片；后端接口和未缓存的逐日产品仍需要网络。


## 首次启动进行测试与网络说明

推荐新建名为 `FieldMoist` 的 Conda 环境；在线模式首次使用前，在 `.env` 设置 `EARTH_ENGINE_PROJECT`，运行 `python tools/authorize_earth_engine.py` 完成 GEE 首次认证。认证和在线下载需要能够访问 Google Earth Engine 的网络。

数据包解压后先运行 `python backend/manage.py validate_fieldmoist_data --dataset all`。网页中选择 Offline，输入 `test`，等待测试预设加载并点击“开始处理”，该流程只使用本地测试数据。
# PNG 展示与 test 重算

彩色 PNG 通过本地服务直接显示，不依赖高德瓦片或 ImageLayer。高德不可用时仍可查看已有产品。

每次启动离线 `test` 均清理该测试的预处理副本、周期缓存、完成标记和旧 TIF/PNG，再从原始输入运行；保留输入、共享模型和 NASA 缓存。
更新程序后重启前后端即可，无需删除数据库或重新登记 83。

选点圆圈显示在彩色 PNG 上方；高德脚本不可用时也可在本地产品上选点。
