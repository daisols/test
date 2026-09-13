import os
import shutil
from datetime import timedelta
from time import sleep

from images.models import ImageDownloadTask
from images.tools import process_satellite_imagery_with_mosaic
from polygons.models import Polygon
from .function1.pipeline import step2
from .function2.pipeline import step1
from .function3.adapter import step3, _normalize_result_filenames
from .sucdeal import batch_color_tifs


def transform_tif(
        base_dir,
        # step1
        model_LAI_pkl,
        model_ALA_pkl,
        model_CWC_pkl,
        # step2
        coarse_tif,
        clay_tif,
        sand_tif,
        rongzhong_tif,
        AIEM_Dobson_pkl,
        # step3
        shp_dir,
        #
        threshold=0.05,
        interp_method="cubic",  # ["linear", "nearest", "cubic", "quadratic", "slinear"],
        filter_type='sg',  # ["none", "mean", "median", "gaussian", "sg"]
        sg_window=7,  # Filter window size.
        sg_order=2,  # Filter polynomial order.
        n_threads=os.cpu_count(),
        soil_moisture_dir=None,
        excel_path=None,
        g_mode='inverse',
        ignore_fusion_marker=False,
        model_path=None,
        ml_share_model=True,
):
    try:
        markers = [os.path.join(base_dir, '.stage1.complete'), os.path.join(base_dir, '.stage2.complete')]
        # A supplied soil-moisture raster is the old f_moisture_content output;
        # skip preprocessing/function1/function2 and go straight to upgraded G.
        if soil_moisture_dir is None:
            if not os.path.exists(markers[0]):
                step1(base_dir, model_LAI_pkl, model_ALA_pkl, model_CWC_pkl,
                      threshold, interp_method, filter_type, sg_window, sg_order, n_threads)
                open(markers[0], 'a', encoding='utf-8').close()
            if not os.path.exists(markers[1]):
                step2(base_dir, coarse_tif, [clay_tif, sand_tif, rongzhong_tif], AIEM_Dobson_pkl)
                open(markers[1], 'a', encoding='utf-8').close()
            soil_moisture_dir = os.path.join(base_dir, 'soil_moisture_1')
        fusion_marker = os.path.join(base_dir, '.fusion.complete')
        # Keep the original marker behavior for normal projects.  The bundled
        # test preset intentionally ignores .fusion.complete so its direct
        # inverse + Excel patch workflow always runs when Start is clicked.
        fusion_ready = os.path.exists(fusion_marker) and not ignore_fusion_marker
        if not fusion_ready:
            step3(base_dir, shp_dir, soil_moisture_dir=soil_moisture_dir,
                  g_mode=g_mode, excel_path=excel_path,
                  model_path=model_path, ml_share_model=ml_share_model,
                  ml_fallback_to_inverse=(os.getenv('FIELDMOIST_G_ML_FALLBACK_TO_INVERSE', 'true').lower() not in {'0', 'false', 'no'}))
            open(fusion_marker, 'a', encoding='utf-8').close()
    except Exception as e:
        raise  e

from config.settings import MEDIA_ROOT
from result_img.models import ResultImg
from images.models import SatelliteImage
from django.utils import timezone

# Keep intermediate processing artifacts by default.  The process directory
# contains Fourier/interpolation/solver outputs used for diagnostics and for
# resuming an interrupted job.  Set this to True only when an explicit cleanup
# is desired after a successful run.
cleanup_workspace = False
not_install = False
from .predeal.pipeline import predeal_sentinel1_tif,predeal_sentinel2_tif,predeal_smap_tif
def run(instance : ResultImg):
    def update_progress(status, process):
        instance.status = status
        instance.process = process
        instance.save(update_fields=['status', 'process'])

    polygon_id = instance.polygon.id
    start_day = instance.start_day.strftime('%Y-%m-%d')
    end_day = instance.end_day.strftime('%Y-%m-%d')
    # Earth Engine uses an exclusive end date. Keep the requested range on
    # ResultImg, but process an inclusive range padded to a complete 12-day
    # batch so interpolation has the context it expects.
    requested_start = instance.start_day
    requested_end = instance.end_day
    requested_days = (requested_end - requested_start).days + 1
    padded_days = ((requested_days + 11) // 12) * 12
    processing_end = requested_start + timedelta(days=padded_days - 1)
    processing_end_day = processing_end.strftime('%Y-%m-%d')
    base_dir = os.path.join(MEDIA_ROOT, 'images', str(polygon_id), f'{start_day}_{end_day}')
    task = ImageDownloadTask.objects.filter(
        polygon_id=polygon_id,
        start_day=requested_start,
        end_day=processing_end,
    ).order_by('-created_at').first()
    if task is None:
        task = ImageDownloadTask.objects.create(
        name=f"{Polygon.objects.get(id=polygon_id).name}: imagery from {start_day} to {end_day}",
        polygon=Polygon.objects.get(id=polygon_id),
        start_day=start_day,
        end_day=processing_end_day,
        )
    elif task.status == 'completed':
        task.error_message = None
        task.save(update_fields=['error_message', 'updated_at'])
    task.save()
    if instance.generation_mode == 'offline' and polygon_id == 82 and instance.polygon.name.lower() == 'test':
        from service.test_workspace import reset_test_workspace
        try:
            reset_test_workspace(base_dir)
        except (OSError, ValueError) as exc:
            task.status = 'failed'
            task.error_message = f'Could not prepare a clean test workspace: {exc}'
            task.save(update_fields=['status', 'error_message'])
            update_progress('failed', 0)
            return
    update_progress('downloading', 5)
    print("读取本地数据" if instance.generation_mode == "offline" else "下载影像数据", flush=True)
    if instance.generation_mode == 'offline':
        task.status = 'completed'
        task.progress = 100
        task.error_message = None
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'progress', 'error_message', 'completed_at', 'updated_at'])
    elif not not_install:
        # The downloader catches its own exceptions and returns a result object.
        # Do not continue into preprocessing when Earth Engine (or another
        # source) could not be reached: there would be no input imagery and the
        # eventual error would hide the actual cause of the failure.
        download_result = process_satellite_imagery_with_mosaic(task)
        if not download_result or not download_result.get('success'):
            message = (
                download_result.get('message')
                if isinstance(download_result, dict)
                else 'Satellite imagery download failed.'
            ) or 'Satellite imagery download failed.'
            task.status = 'failed'
            task.progress = 0
            task.error_message = message
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'progress', 'error_message', 'completed_at', 'updated_at'])
            update_progress('failed', 0)
            print("下载失败，请查看任务提示", flush=True)
            return
    task.progress = 10
    task.save()
    update_progress('preprocessing', 20)
    print("预处理影像", flush=True)
    has_local_moisture = bool(instance.local_moisture_dir)
    s1 = SatelliteImage.objects.filter(polygon=polygon_id, satellite='sentinel-1').filter(shoot_time__range=[start_day, processing_end_day])
    s2 = SatelliteImage.objects.filter(polygon=polygon_id, satellite='sentinel-2').filter(shoot_time__range=[start_day, processing_end_day])
    smap = SatelliteImage.objects.filter(polygon=polygon_id, satellite='smap').filter(shoot_time__range=[start_day, processing_end_day])
    if not has_local_moisture:
        for i in s1:
            output = os.path.join(base_dir, 'org_sentinel1', os.path.basename(i.image.path))
            if not os.path.exists(output):
                predeal_sentinel1_tif(i.image.path, os.path.join(base_dir, 'org_sentinel1'))
        for i in s2:
            output = os.path.join(base_dir, 'org_sentinel2', os.path.basename(i.image.path))
            if not os.path.exists(output):
                predeal_sentinel2_tif(i.image.path, os.path.join(base_dir, 'org_sentinel2'))
    for i in smap:
        output = os.path.join(base_dir, 'org_smap', os.path.basename(i.image.path))
        if not os.path.exists(output):
            predeal_smap_tif(i.image.path, os.path.join(base_dir, 'org_smap'))

    # Stop if any required preprocessed image directory contains fewer than two files.
    if (not has_local_moisture and (
        len(os.listdir(os.path.join(base_dir, 'org_sentinel1'))) < 2 or
        len(os.listdir(os.path.join(base_dir, 'org_sentinel2'))) < 2
    )) or len(os.listdir(os.path.join(base_dir, 'org_smap'))) < 2:
        task.progress = 0
        task.status = 'failed'
        task.error_message = 'Insufficient preprocessed imagery for the selected date range.'
        task.completed_at = timezone.now()
        task.save(update_fields=['progress', 'status', 'error_message', 'completed_at', 'updated_at'])
        update_progress('failed', 0)
        return
    update_progress('solving', 35)
    print("计算土壤水分", flush=True)
    # step1
    model_LAI_pkl = os.path.join(MEDIA_ROOT, 'model', 'model_LAI.pkl')
    model_ALA_pkl = os.path.join(MEDIA_ROOT, 'model', 'model_ALA.pkl')
    model_CWC_pkl = os.path.join(MEDIA_ROOT, 'model', 'model_CWC.pkl')
    # step2
    coarse_tif = os.path.join(MEDIA_ROOT,'mask_tif','coarse.tif')
    Clay_tif = os.path.join(MEDIA_ROOT, 'Clay_Sand_RongZhong_tifs', 'Clay.tif')
    Sand_tif = os.path.join(MEDIA_ROOT, 'Clay_Sand_RongZhong_tifs', 'Sand.tif')
    RongZhong_tif = os.path.join(MEDIA_ROOT, 'Clay_Sand_RongZhong_tifs', 'RongZhong.tif')
    AIEM_Dobson_pkl = os.path.join(MEDIA_ROOT, 'model', 'AIEM_Dobson.pkl')
    # step3
    shp_dir = os.path.join(MEDIA_ROOT, 'images', str(polygon_id), 'shp')
    try:
        local_moisture_dir = None
        if instance.local_moisture_dir:
            local_moisture_dir = os.path.join(MEDIA_ROOT, instance.local_moisture_dir)
        measurement_excel_path = None
        if instance.measurement_excel_path:
            measurement_excel_path = os.path.join(MEDIA_ROOT, instance.measurement_excel_path)
        transform_tif(
            base_dir,
            # step1
            model_LAI_pkl,
            model_ALA_pkl,
            model_CWC_pkl,
            # step2
            coarse_tif,
            Clay_tif,
            Sand_tif,
            RongZhong_tif,
            AIEM_Dobson_pkl,

            # step3
            shp_dir,
            #
            threshold=0.05,
            interp_method="cubic",
            filter_type='sg',
            sg_window=7,
            sg_order=2,
            n_threads=os.cpu_count(),
            soil_moisture_dir=local_moisture_dir,
            excel_path=measurement_excel_path,
            g_mode=(
                os.getenv('FIELDMOIST_G_MODE')
                if os.getenv('FIELDMOIST_G_MODE') in {'inverse', 'patch_excel', 'ml_all'}
                else (
                    'patch_excel'
                    if measurement_excel_path else 'inverse'
                )
            ),
            ignore_fusion_marker=(
                instance.generation_mode == 'offline'
                and instance.polygon_id == 82
                and str(instance.polygon.name).lower() == 'test'
            ),
            model_path=(
                os.getenv('FIELDMOIST_G_ML_MODEL_PATH')
                or (
                    os.path.join(base_dir, 'process', 'shared_ml_model_rf.pkl')
                    if instance.generation_mode == 'offline'
                    and instance.polygon_id == 82
                    and str(instance.polygon.name).lower() == 'test'
                    else None
                )
            ),
            ml_share_model=(os.getenv('FIELDMOIST_G_ML_SHARE_MODEL', 'true').lower() not in {'0', 'false', 'no'}),
        )
    except Exception as e:
        print("计算失败，请查看任务提示", flush=True)
        task.progress = 0
        task.status = 'failed'
        task.error_message = str(e)
        task.completed_at = timezone.now()
        task.save(update_fields=['progress', 'status', 'error_message', 'completed_at', 'updated_at'])
        update_progress('failed', 0)
        return
    update_progress('colorizing', 90)
    print("生成彩色产品", flush=True)
    batch_color_tifs(
        input_dir=os.path.join(base_dir, 'soil_moisture_result'),
        output_dir=os.path.join(base_dir, 'soil_moisture_png'),
        cmap_name="CB-RdBu",
         minValue=0.0,
         maxValue=0.4,
         shp_dir=shp_dir,
    )
    # Keep the public PNG names date-based as well, even when source SMAP
    # filenames contain a project/satellite prefix.
    _normalize_result_filenames(os.path.join(base_dir, 'soil_moisture_png'))
    update_progress('completed', 100)
    print("处理完成", flush=True)
    # Keep the workspace (especially ``process``) by default.  These
    # intermediates are needed to inspect a run and to resume it without
    # recomputing completed stages.  Cleanup remains available as an explicit
    # opt-in by setting ``cleanup_workspace = True`` above.
    if cleanup_workspace:
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)

            if item in {'soil_moisture_result', 'soil_moisture_png'}:
                continue
            if os.path.isfile(item_path):
                if not (item.lower().endswith('.tif') or item.lower().endswith('.tiff')):
                    os.remove(item_path)
            else:
                shutil.rmtree(item_path, ignore_errors=True)

def main():
    pass


if __name__ == '__main__':
    main()

