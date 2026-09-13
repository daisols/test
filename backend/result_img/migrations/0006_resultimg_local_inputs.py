from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('result_img', '0005_resultimg_generation_mode')]
    operations = [
        migrations.AddField(
            model_name='resultimg', name='local_moisture_dir',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='resultimg', name='measurement_excel_path',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
