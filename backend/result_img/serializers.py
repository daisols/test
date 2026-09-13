from rest_framework import serializers

from polygons.models import Polygon
from result_img.models import ResultImg


class ResultImgCreateSerializer(serializers.ModelSerializer):
    polygon = serializers.PrimaryKeyRelatedField(
        queryset=Polygon.objects.all(),
        error_messages={'does_not_exist': 'The specified polygon does not exist.'}
    )

    class Meta:
        model = ResultImg
        fields = ['polygon', 'start_day', 'end_day', 'generation_mode']
        extra_kwargs = {
            'polygon': {'required': True},
            'start_day': {'required': True},
            'end_day': {'required': True},
            'generation_mode': {'required': False},
        }

    def validate(self, data):
        if data['start_day'] > data['end_day']:
            raise serializers.ValidationError('The start date must not be after the end date.')
        return data


class ResultImgSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultImg
        fields = ['id', 'polygon', 'start_day', 'end_day', 'process', 'status', 'generation_mode', 'local_moisture_dir', 'measurement_excel_path']

class ResultImgListSerializer(serializers.ModelSerializer):
    polygon = serializers.PrimaryKeyRelatedField(
        queryset=Polygon.objects.all(),
        error_messages={'does_not_exist': 'The specified polygon does not exist.'}
    )
    class Meta:
        model = ResultImg
        fields = ['id','polygon', 'start_day', 'end_day', 'process']
        extra_kwargs = {
            'polygon': {'required': True},
        }

class ResultImgDeleteSerializer(serializers.ModelSerializer):
    polygon = serializers.PrimaryKeyRelatedField(
        queryset=Polygon.objects.all(),
        error_messages={'does_not_exist': 'The specified polygon does not exist.'}
    )
    class Meta:
        model = ResultImg
        fields = ['polygon', 'start_day', 'end_day']
        extra_kwargs = {
            'polygon': {'required': True},
        }
