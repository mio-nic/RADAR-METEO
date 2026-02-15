import requests
import rasterio
import os
import geopandas as gpd
from rasterio.features import shapes

# Configurazione API
BASE_URL = "https://radar-api.protezionecivile.it"

def update_radar():
    try:
        # 1. Chiedi l'ultimo prodotto disponibile (VMI = Vertical Maximum Intensity)
        print("Verifica ultimo timestamp...")
        res_last = requests.get(f"{BASE_URL}/findLastProductByType?type=VMI")
        res_last.raise_for_status()
        data_last = res_last.json()
        
        last_time = data_last['lastProducts'][0]['time']
        print(f"Ultimo dato disponibile alle: {last_time}")

        # 2. Chiedi l'URL pre-firmato per il download
        print("Richiesta URL di download...")
        res_dl = requests.post(
            f"{BASE_URL}/downloadProduct",
            json={"productType": "VMI", "productDate": last_time}
        )
        res_dl.raise_for_status()
        download_url = res_dl.json()['url']

        # 3. Scarica il file TIF
        print("Scaricamento file radar...")
        tif_data = requests.get(download_url)
        with open("radar_temp.tif", "wb") as f:
            f.write(tif_data.content)

        # 4. Elaborazione GIS (come prima)
        with rasterio.open("radar_temp.tif") as src:
            image = src.read(1)
            mask = (image > 0) & (image < 255)
            results = (
                {'properties': {'mm': float(v)}, 'geometry': s}
                for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform))
            )
            
            df = gpd.GeoDataFrame.from_features(list(results))
            if not df.empty:
                df.crs = src.crs
                
                
                if not os.path.exists('data'):
                    os.makedirs('data')
                
                veneto.to_crs(epsg=4326).to_file("data/pioggia_veneto.json", driver='GeoJSON')
                print("Successo! File pioggia_veneto.json aggiornato.")
            else:
                print("Nessuna pioggia rilevata.")

    except Exception as e:
        print(f"ERRORE: {e}")

if __name__ == "__main__":
    update_radar()
