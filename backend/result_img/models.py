from django.db import models
from polygons.models import Polygon
# Create your models here.
class ResultImg(models.Model):
    polygon = models.ForeignKey(Polygon, on_delete=models.CASCADE)
    start_day = models.DateField()
    end_day = models.DateField()
    result_dir = models.CharField(max_length=200)
    process = models.IntegerField(default=0)
    status = models.CharField(default='Waiting', max_length=20)
    generation_mode = models.CharField(
        max_length=20,
        choices=[('online', 'Online'), ('offline', 'Offline')],
        default='online',
    )
    local_moisture_dir = models.CharField(max_length=255, blank=True, null=True)
    measurement_excel_path = models.CharField(max_length=255, blank=True, null=True)
    is_delete = models.BooleanField(default=False)
    class Meta:
        db_table = 'result_img'
        verbose_name = 'Result image set'
        constraints = [
            models.UniqueConstraint(
                fields=['polygon', 'start_day', 'end_day'],
                condition=models.Q(is_delete=False),
                name='unique_result_img_active'
            )
        ]
