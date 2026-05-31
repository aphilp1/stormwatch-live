"""Re-pull Thomas ERA5 with southern boundary extended to 34N so VBG is inside."""
import cdsapi, os

client = cdsapi.Client()
target = "./era5/era5_pl_thomas_2017.nc"
if os.path.exists(target):
    os.remove(target)
    print(f"removed old {target}")

req = {
    "product_type": ["reanalysis"],
    "variable": ["u_component_of_wind","v_component_of_wind",
                 "geopotential","temperature","relative_humidity"],
    "pressure_level": ["500","700","850","925","1000"],
    "year": ["2017"], "month": ["12"], "day": ["04","05","06"],
    "time": [f"{h:02d}:00" for h in range(24)],
    "area": [42.0, -124.0, 34.0, -117.0],   # S extended to 34N (was 35N)
    "data_format": "netcdf",
}
print("Pulling Thomas with S=34N ...")
client.retrieve("reanalysis-era5-pressure-levels", req, target)
print(f"Done -> {target} ({os.path.getsize(target)//1024} KB)")
