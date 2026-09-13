from rest_framework import serializers
from .models import ImageDownloadTask, SatelliteImage
from polygons.models import Polygon
from polygons.serializers import PolygonSerializer


class SatelliteImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SatelliteImage
        fields = '__all__'
        read_only_fields = ('created_at',)


class SatelliteImageListSerializer(serializers.ModelSerializer):
    'Compact serializer for list views.'

    class Meta:
        model = SatelliteImage
        fields = (
            'id',
            'name',
            'shoot_time',
            'satellite',
            'image',
            'file_size',
            'cloud_coverage',
            'created_at'
        )


class ImageDownloadTaskSerializer(serializers.ModelSerializer):
    # Serialize nested polygon information.
    polygon = PolygonSerializer(read_only=True)
    # Serialize the associated images.
    images = SatelliteImageSerializer(many=True, read_only=True)

    class Meta:
        model = ImageDownloadTask
        fields = '__all__'
        read_only_fields = (
            'created_at',
            'updated_at',
            'completed_at',
            'status',
            'progress',
            'error_message',
            'downloaded_images_count'
        )


class ImageDownloadTaskCreateSerializer(serializers.ModelSerializer):
    # Creation requires only the polygon ID.
    polygon_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = ImageDownloadTask
        fields = (
            'id',
            'name',
            'polygon_id',
            'start_day',
            'end_day',
        )

    def validate_polygon_id(self, value):
        'Verify that the polygon ID exists.'
        try:
            Polygon.objects.get(id=value)
        except Polygon.DoesNotExist:
            raise serializers.ValidationError("指定的多边形不存在")
        return value

    def create(self, validated_data):
        'Create a download task.'
        polygon_id = validated_data.pop('polygon_id')
        polygon = Polygon.objects.get(id=polygon_id)
        validated_data['polygon'] = polygon

        # Call the parent serializer's create method.
        return super().create(validated_data)


class ImageDownloadTaskUpdateSerializer(serializers.ModelSerializer):
    'Serializer for download task status updates.'

    class Meta:
        model = ImageDownloadTask
        fields = (
            'status',
            'progress',
            'error_message',
            'downloaded_images_count',
            'completed_at'
        )
