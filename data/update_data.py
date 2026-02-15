import requests
import datetime
import rasterio
from rasterio.features import shapes
import geopandas as gpd
import os

def get_latest_radar():
    # 1. Calcola l'ultimo slot disponibile (ogni 10 min: 05, 15, 25, 35, 45, 55)
    # Usiamo un ritardo di 15 minuti per essere sicuri che il file sia stato caricato
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
    
    # Arrotonda ai 5 minuti (il DPC pubblica spesso con finale 5)
    minute = (now.minute // 10) * 10 + 5
    if minute > 55: minute = 55
    
    timestamp = now.strftime(f"%d-%m-%Y-%H-{minute:02d}")
    # URL pubblico S3 (senza firma, accessibile dallo script)
    url = f"https://dpc-radar.s3.eu-south-1.amazonaws.com/VMI/{timestamp}.tif"
    
    print(f"Tentativo download: {url}")
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            with open("radar.tif", "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"Errore {r.status_code}: Il file non è ancora pronto.")
            return False
    except Exception as e:
        print(f"Errore connessione: {e}")
        return False

def process_to_geojson():
    # Converte il raster TIF in un GeoJSON leggero solo per il Veneto
    with rasterio.open("radar.tif") as src:
        image = src.read(1)
        # Maschera: escludi valori zero (no pioggia) e valori di errore (es. 255)
        mask = (image > 0) & (image < 250)
        
        results = (
            {'properties': {'mm': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform))
        )
        
        df = gpd.GeoDataFrame.from_features(list(results))
        df.crs = src.crs
        
        # Filtro geografico (Bounding Box Veneto)
        # Coordinate approssimative per ritagliare solo l'area di interesse
        veneto_bbox = df.cx[10.5:13.1, 44.7:46.7]
        
        if not os.path.exists('data'): os.makedirs('data')
        # Esporta in WGS84 per Leaflet
        veneto_bbox.to_crs(epsg=4326).to_file("data/pioggia_veneto.json", driver='GeoJSON')
        print("Mappa aggiornata!")

if get_latest_radar():
    process_to_geojson()
