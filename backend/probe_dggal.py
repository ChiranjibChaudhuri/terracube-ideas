
import sys
from dggal import Application, pydggal_setup, IVEA3H, GeoPoint, nullZone

app = None
def _init():
    global app
    app = Application(appGlobals=globals())
    pydggal_setup(app)

def probe():
    _init()
    dggrs = IVEA3H()
    print("Methods of IVEA3H:", dir(dggrs))
    
    try:
        pt = GeoPoint(lat=40.7128, lon=-74.0060)
        # Check methods for zone/point conversion
        # Common names: getZone, getZoneFromGeoPoint
        
        # Method 2: Use listZones with epsilon
        from dggal import GeoExtent
        
        eps = 0.000001
        extent = GeoExtent()
        extent.ll = GeoPoint(lat=40.7128 - eps, lon=-74.0060 - eps)
        extent.ur = GeoPoint(lat=40.7128 + eps, lon=-74.0060 + eps)
        
        print("Listing zones for epsilon extent...")
        zones = dggrs.listZones(7, extent)
        if zones:
            for z in zones:
                print(f"Found zone: {dggrs.getZoneTextID(z)}")
        else:
            print("No zones found via listZones.")
                 
    except Exception as e:
        print("Error testing point:", e)

if __name__ == "__main__":
    probe()
