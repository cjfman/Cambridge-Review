import json
from shapely.geometry import shape, Point

class GisGeoJson:
    def __init__(self, path, *, secondary_id_key=None):
        self.geojson          = None
        self.secondary_id_key = secondary_id_key
        self.id_to_secondary  = {}
        self.secondary_to_id  = {}
        self.features         = {}
        with open(path) as f:
            self.geojson = json.load(f)

        self.features = { x['id']: x for x in self.geojson['features'] }
        if self.secondary_id_key is not None:
            for feature in self.geojson['features']:
                sec_id = feature['properties'][self.secondary_id_key]
                geo_id = feature['id']
                self.secondary_to_id[sec_id] = geo_id
                self.id_to_secondary[geo_id] = sec_id

    def findAllFeatures(self, point):
        if not isinstance(point, Point):
            point = Point(point)

        found = []
        for feature in self.geojson['features']:
            polygon = shape(feature['geometry'])
            if polygon.contains(point):
                found.append(feature)

        return found

    def findFeature(self, point):
        found = self.findAllFeatures(point)
        if not found:
            return None

        return found[0]

    def getGeoId(self, sec_id):
        if sec_id not in self.secondary_to_id:
            return None

        return self.secondary_to_id[sec_id]

    def setProperty(self, key, val, geo_id=None):
        if geo_id is not None:
            self.features[geo_id]['properties'][key] = val
        else:
            for f in self.features.values():
                f['properties'][key] = val


class ZoningDistricts(GisGeoJson):
    def __init__(self, path):
        GisGeoJson.__init__(self, path, secondary_id_key='ZONE_TYPE')

    def findZone(self, point):
        found = self.findFeature(point)
        if not found:
            return None

        return found['properties']['ZONE_TYPE']


class CityBlocks(GisGeoJson):
    def __init__(self, path):
        GisGeoJson.__init__(self, path, secondary_id_key='UNQ_ID')

    def findBlock(self, point):
        found = self.findFeature(point)
        if not found:
            return None

        return found['properties']['UNQ_ID']

class Lots(GisGeoJson):
    def __init__(self, path):
        GisGeoJson.__init__(self, path, secondary_id_key='ML')
