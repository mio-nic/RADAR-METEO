import requests
import rasterio
import os
import geopandas as gpd
from rasterio.features import shapes
import numpy as np

BASE_URL = "https://radar-api.protezionecivile.it"

def update_radar():
    try:
        # 1. Recupero l'ultimo timestamp disponibile per la cumulata 24 ore
        print("Controllo disponibilità CUM24...")
        res_last = requests.get(f"{BASE_URL}/findLastProductByType?type=CUM24", timeout=30)
        res_last.raise_for_status()
        data = res_last.json()
        
        if not data.get('lastProducts'):
            print("Nessun prodotto trovato.")
            return

        last_time = data['lastProducts'][0]['time']

        # 2. Richiesta URL di download
        print(f"Timestamp: {last_time}. Richiesta URL...")
        res_dl = requests.post(f"{BASE_URL}/downloadProduct", 
                               json={"productType": "CUM24", "productDate": last_time},
                               timeout=30)
        res_dl.raise_for_status()
        download_url = res_dl.json().get('url')

        # 3. Download del file TIF
        print("Download del file radar...")
        tif_data = requests.get(download_url, timeout=60)
        with open("radar_temp.tif", "wb") as f:
            f.write(tif_data.content)

        # 4. Elaborazione GIS
        with rasterio.open("radar_temp.tif") as src:
            image = src.read(1)
            # Maschera: prendiamo solo valori di pioggia significativi (es. > 0.5mm)
            mask = (image > 0.5) & (image < 200)
            
            # Generazione poligoni dalle aree di pioggia
            results = ({'properties': {'mm': float(v)}, 'geometry': s} 
                       for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform)))
            
            df = gpd.GeoDataFrame.from_features(list(results))
            
            if not df.empty:
                print(f"Dati estratti. Inizio ottimizzazione di {len(df)} poligoni...")
                df.crs = src.crs
                df = df.to_crs(epsg=4326)

                # --- OTTIMIZZAZIONE PER GITHUB (Sotto i 100MB) ---
                # 1. Arrotondiamo i valori per raggruppare piogge simili
                df['mm'] = df['mm'].round(0).astype(int)
                
                # 2. Dissolve: uniamo i poligoni che hanno lo stesso valore di 'mm'
                df = df.dissolve(by='mm').reset_index()

                # 3. Simplify: riduciamo il numero di punti dei poligoni (precisione ~1km)
                df['geometry'] = df['geometry'].simplify(0.01, preserve_topology=True)
                
                # 4. Filtro area: rimuoviamo poligoni piccolissimi (rumore)
                df = df[df.geometry.area > 0.0001]
                # ------------------------------------------------

                # Creazione cartella e salvataggio
                if not os.path.exists('data'):
                    os.makedirs('data')
                
                output_path = "data/pioggia_veneto.json"
                df.to_file(output_path, driver='GeoJSON')
                
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"Successo! File salvato: {output_path} ({size_mb:.2f} MB)")
            else:
                print("Nessuna pioggia rilevata nelle ultime 24 ore.")
                if not os.path.exists('data'):
                    os.makedirs('data')
                with open("data/pioggia_veneto.json", "w") as f:
                    f.write('{"type":"FeatureCollection","features":[]}')

    except Exception as e:
        print(f"ERRORE: {str(e)}")

if __name__ == "__main__":
    update_radar()
