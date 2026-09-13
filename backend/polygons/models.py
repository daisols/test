from django.db import models

class Polygon(models.Model):
    id = models.AutoField(primary_key=True, editable=False)
    name = models.CharField(max_length=100, unique=True)
    gcj02_coordinates = models.JSONField()
    wgs84_coordinates = models.JSONField(blank=True, null=True)
    wgs84_shp_dir = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'polygon'
        ordering = ['id']
        verbose_name = 'Polygon'