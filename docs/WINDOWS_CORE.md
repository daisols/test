# Windows Core Installation

The public application and private compiled core are two repositories.
The public repository contains Django and Vue code, environment templates,
tests, documentation and an installer. The private repository contains the
Windows extensions, empty package initializers, manifest and binary license.
Neither contains algorithm source. The companion dataset is provided separately.

Supported runtime: Windows 10/11 x64 and CPython 3.12 x64. Linux, macOS,
Windows ARM64 and other Python minor versions are not supported.

## Install

Obtain authorized access to the matching private core version. Extract the
public and private checkouts into adjacent folders, then run from public:

```powershell
conda env create -f environment.yml
conda activate FieldMoist
python tools/install_core.py --from-dir ../private
python tools/smoke_native_core.py
```

The installer verifies the SHA-256 manifest, validates module names and paths,
and copies native files under `backend/service/transform_tif/_native/`. It copies
the private license to `backend/service/transform_tif/CORE_LICENSE.txt`.
Those installed files are ignored by the public repository. To install a different
core version, stop the backend and run the installer with --upgrade.
No core source, compiler or Cython installation is needed.

Then follow STARTUP.md to configure credentials, place data, migrate, initialize
jiefangzha and run the offline test. GEE authentication is needed for Online
mode only. Without authorized private core access the full backend cannot run.
