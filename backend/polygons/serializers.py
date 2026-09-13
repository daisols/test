from rest_framework import serializers
from .models import Polygon
from .tools import transform_coordinates, wgs84_to_gcj02

class PolygonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Polygon
        fields = '__all__'


class PolygonCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Polygon
        fields = '__all__'
        extra_kwargs = {
            'gcj02_coordinates': {'required': False},
            'wgs84_coordinates': {'required': False},
        }

    def validate(self, attrs):
        gcj_coordinates = attrs.get('gcj02_coordinates')
        wgs_coordinates = attrs.get('wgs84_coordinates')
        if gcj_coordinates:
            if len(gcj_coordinates) == 1:
                gcj_coordinates = gcj_coordinates[0]
            attrs['gcj02_coordinates'] = gcj_coordinates
            attrs['wgs84_coordinates'] = transform_coordinates(gcj_coordinates)
        elif wgs_coordinates:
            if len(wgs_coordinates) == 1:
                wgs_coordinates = wgs_coordinates[0]
            attrs['wgs84_coordinates'] = wgs_coordinates
            attrs['gcj02_coordinates'] = [list(wgs84_to_gcj02(*point)) for point in wgs_coordinates]
        else:
            raise serializers.ValidationError('Provide GCJ-02 or WGS84 boundary coordinates.')
        if len(attrs['wgs84_coordinates']) < 3:
            raise serializers.ValidationError('A field boundary requires at least three vertices.')
        return attrs
