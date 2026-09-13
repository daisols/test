from django.db import models
from polygons.models import Polygon

ALLOWED_SATELLITES = [
    'sentinel-1',
    'sentinel-2',
    'smap'
]
# Satellite image collections.
COLLECTION_MAP = {
    'sentinel-2': 'COPERNICUS/S2_SR_HARMONIZED',  #
    'sentinel-1': 'COPERNICUS/S1_GRD',  #
    'smap': 'NASA/SMAP/SPL4SMGP/008',
    # Add other satellites here as needed.
}
SATELLITE_BANDS = {
    'sentinel-1': ['VV','VH','angle'],
    'sentinel-2': ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12','SCL'],
    'smap': ['sm_surface']
}

class ImageDownloadTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('downloading', 'Downloading'),
        ('completed', 'Completed'),
        ('partial_completed', 'Partially completed'),
        ('failed', 'Failed'),
    ]

    id = models.AutoField(primary_key=True, editable=False)
    name = models.CharField(max_length=200, help_text='Task name', default='Untitled task')

    # Core parameters.
    polygon = models.ForeignKey(
        Polygon,
        on_delete=models.CASCADE,
        related_name='download_tasks',
        help_text='Target polygon area'
    )
    start_day = models.DateField(help_text='Start of date range')
    end_day = models.DateField(help_text='End of date range')

    # Task status.
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Task status',
        blank=True,
        null = True,

    )
    progress = models.IntegerField(
        default=0,
        help_text='Download progress (percent)',
    )

    # Metadata.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True, help_text='Completion time')

    # Error handling.
    error_message = models.TextField(blank=True, null=True, help_text='Error message')

    # Download results.
    downloaded_images_count = models.IntegerField(blank=True, null=True, default=0, help_text='Downloaded image count')

    class Meta:
        db_table = 'image_download_tasks'
        ordering = ['-created_at']
        verbose_name = 'Image download task'
        verbose_name_plural = 'Image download tasks'

    def __str__(self):
        return f"{self.name}"


class SatelliteImage(models.Model):
    id = models.AutoField(primary_key=True, editable=False)

    # Associated polygon.
    polygon = models.ForeignKey(
        Polygon,
        on_delete=models.CASCADE,
        related_name='images',
        help_text='Associated polygon area'
    )

    # Image information.
    name = models.CharField(max_length=100, help_text='Image name')
    shoot_time = models.DateField(help_text='Acquisition date')
    satellite = models.CharField(
        max_length=100,
        choices=[(sat, sat) for sat in ALLOWED_SATELLITES],
        help_text='Satellite type'
    )

    # File information.
    image = models.ImageField(upload_to='images/', blank=True, null=True, help_text='Image file')
    file_size = models.BigIntegerField(blank=True, null=True, help_text='File size (bytes)')

    # Metadata.
    created_at = models.DateTimeField(auto_now_add=True)

    # Satellite-specific information.
    image_identifier = models.CharField(max_length=200, blank=True, null=True, help_text='Satellite image identifier')
    download_url = models.URLField(blank=True, null=True, help_text='Source download URL')

    class Meta:
        db_table = 'satellite_images'
        ordering = ['-shoot_time']
        verbose_name = 'Satellite image'
        verbose_name_plural = 'Satellite images'

    def __str__(self):
        return f"{self.name} ({self.shoot_time.strftime('%Y-%m-%d')})"
