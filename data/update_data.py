import requests
import datetime
import rasterio
from rasterio.features import shapes
import geopandas as gpd
import os

def run():
    # Creiamo la cartella data se manca
    if not os.path.exists('data'):
        os.makedirs('data')

    # Proviamo a scaricare il radar (Margine di 20 min per sicurezza)
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=20)
    minute = (now.minute // 10) * 10 + 5
    timestamp = now.strftime(f"%d-%m-%Y-%H-{minute:02d}")
    url = f"https://dpc-radar.s3.eu-south-1.amazonaws.com/VMI/{timestamp}.tif"
    
    print(f"Scarico: {url}")
    r = requests.get(url)

    if r.status_code != 200:
        print("Radar non trovato. Creo file vuoto per evitare 404.")
        with open("data/pioggia_veneto.json", "w") as f:
            f.write('{"type":"FeatureCollection","features":[]}')
        return

    with open("radar.tif", "wb") as f:
        f.write(r.content)

    with rasterio.open("radar.tif") as src:
        image = src.read(1)
        mask = (image > 0) & (image < 255)
        results = ({'properties': {'mm': v}, 'geometry': s} for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform)))
        df = gpd.GeoDataFrame.from_features(list(results))
        
        if len(df) > 0:
            df.crs = src.crs
            # Ritaglio Veneto
            veneto = df.cx[10.5:13.1, 44.7:46.7]
            veneto.to_crs(epsg=4326).to_file("data/pioggia_veneto.json", driver='GeoJSON')
            print("Dati aggiornati correttamente.")
        else:
            with open("data/pioggia_veneto.json", "w") as f:
                f.write('{"type":"FeatureCollection","features":[]}')
            print("Nessuna pioggia, salvato file vuoto.")

run()
