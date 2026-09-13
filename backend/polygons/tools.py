import math


def _outside_china(lng, lat):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng, lat):
    value = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat
    value += 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    value += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    value += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    value += (160.0 * math.sin(lat / 12.0 * math.pi) + 320.0 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return value


def _transform_lng(lng, lat):
    value = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng
    value += 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    value += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 * math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    value += (20.0 * math.sin(lng * math.pi) + 40.0 * math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    value += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 * math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return value


def wgs84_to_gcj02(lng, lat):
    """Convert a WGS84 coordinate to the GCJ-02 system used by AMap."""
    if _outside_china(lng, lat):
        return lng, lat

    semi_major_axis = 6378245.0
    eccentricity = 0.00669342162296594323
    delta_lat = _transform_lat(lng - 105.0, lat - 35.0)
    delta_lng = _transform_lng(lng - 105.0, lat - 35.0)
    latitude_radians = lat / 180.0 * math.pi
    magic = math.sin(latitude_radians)
    magic = 1 - eccentricity * magic * magic
    sqrt_magic = math.sqrt(magic)
    delta_lat = delta_lat * 180.0 / ((semi_major_axis * (1 - eccentricity)) / (magic * sqrt_magic) * math.pi)
    delta_lng = delta_lng * 180.0 / (semi_major_axis / sqrt_magic * math.cos(latitude_radians) * math.pi)
    return lng + delta_lng, lat + delta_lat


def gcj02_to_wgs84(lng, lat):
    'Convert longitude and latitude from GCJ-02 to WGS84 and return the converted pair.'
    a = 6378245.0  # Semi-major axis.
    ee = 0.00669342162296594323  # Flattening coefficient.

    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    d_lat = transform_lat(lng - 105.0, lat - 35.0)
    d_lng = transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - ee * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (a / sqrt_magic * math.cos(rad_lat) * math.pi)
    mg_lat = lat + d_lat
    mg_lng = lng + d_lng
    return lng * 2 - mg_lng, lat * 2 - mg_lat

def transform_coordinates(coordinates):
    'Convert an array of coordinate pairs.'
    return [gcj02_to_wgs84(lng, lat) for lng, lat in coordinates]


import geopandas as gpd
from shapely.geometry import Polygon
import os


def create_polygon_shapefile(coordinates, output_dir, polygon_name,crs="EPSG:4326"):
    'Convert coordinates [[x1, y1], ..., [xn, yn]] to a shapefile. output_path excludes the extension; crs defaults to WGS84 (EPSG:4326).'
    try:
        # Close the polygon by repeating the first point at the end.
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        # Create the polygon object.
        polygon = Polygon(coordinates)

        # Create the GeoDataFrame.
        gdf = gpd.GeoDataFrame(geometry=[polygon], crs=crs)

        # Create the output directory if needed.
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        shp_file = os.path.join(output_dir,polygon_name)
        # Save as a shapefile.
        gdf.to_file(f"{shp_file}.shp")
        print(f"Shapefile已成功创建: {shp_file}.shp")
        print(f"同时生成了辅助文件: .shx, .prj, .dbf等")

    except Exception as e:
        print(f"生成Shapefile时出错: {str(e)}")


if __name__ == "__main__":
    # Polygon coordinates.
    coords = [
        [108.0768497890038, 34.296373838697846],
        [108.03623273460386, 34.281978229827565],
        [108.05113659877424, 34.24819517605636],
        [108.08955456427292, 34.24177217108396],
        [108.10243345356692, 34.265886194503246]
    ]

    # Output path without an extension.
    output_file = "polygon_output"

    # Generate the shapefile.
    create_polygon_shapefile(coords, output_file)
