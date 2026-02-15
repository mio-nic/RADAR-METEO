import requests
import rasterio
import os
import geopandas as gpd
from rasterio.features import shapes
import numpy as np

BASE_URL = "https://radar-api.protezionecivile.it"

def update_radar():
    try:
        # 1. Recupero l'ultimo timestamp per CUM24
        print("Controllo disponibilità CUM24...")
        res_last = requests.get(f"{BASE_URL}/findLastProductByType?type=CUM24", timeout=30)
        res_last.raise_for_status()
        data = res_last.json()
        
        if not data.get('lastProducts'):
            print("Nessun prodotto trovato.")
            return

        last_time = data['lastProducts'][0]['time']

        # 2. Richiesta URL di download
        res_dl = requests.post(f"{BASE_URL}/downloadProduct", 
                               json={"productType": "CUM24", "productDate": last_time},
                               timeout=30)
        res_dl.raise_for_status()
        download_url = res_dl.json().get('url')

        # 3. Download del file radar
        tif_data = requests.get(download_url, timeout=60)
        with open("radar_temp.tif", "wb") as f:
            f.write(tif_data.content)

        # 4. Elaborazione GIS
        with rasterio.open("radar_temp.tif") as src:
            image = src.read(1)
            # Maschera per pioggia (escludiamo valori nulli e bordi mappa)
            mask = (image > 0.5) & (image < 200)
            
            results = ({'properties': {'mm': float(v)}, 'geometry': s} 
                       for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform)))
            
            df = gpd.GeoDataFrame.from_features(list(results))
            
                if not df.empty:
                df.crs = src.crs
                df = df.to_crs(epsg=4326)

                # --- OTTIMIZZAZIONE ALTO DETTAGLIO E SENZA BUCHI ---
                # 1. Arrotondiamo i valori
                df['mm'] = df['mm'].round(1)
                
                # 2. Dissolve per unire i valori uguali
                df = df.dissolve(by='mm').reset_index()

                # 3. TRUCCO DEL BUFFER: chiude i micro-spazi tra i poligoni
                # Espandiamo di un millesimo di grado e contraiamo subito dopo
                df['geometry'] = df['geometry'].buffer(0.001).buffer(-0.001)

                # 4. Semplificazione leggera (mantenendo la topologia per non creare nuovi buchi)
                df['geometry'] = df['geometry'].simplify(0.0005, preserve_topology=True)
                
                # Ritaglio Veneto
                df = df.cx[10.5:13.1, 44.7:46.7]
                
                # Salvataggio
                if not os.path.exists('data'): os.makedirs('data')
                df.to_file("data/pioggia_veneto.json", driver='GeoJSON')
                    df.to_file(output_path, driver='GeoJSON')
                    print(f"Aggiornamento Veneto completato. File: {os.path.getsize(output_path)/1024:.2f} KB")
                else:
                    print("Nessuna pioggia rilevata nell'area del Veneto.")
                    crea_file_vuoto()
            else:
                print("Nessuna pioggia rilevata in Italia.")
                crea_file_vuoto()

    except Exception as e:
        print(f"ERRORE: {str(e)}")

def crea_file_vuoto():
    if not os.path.exists('data'): os.makedirs('data')
    with open("data/pioggia_veneto.json", "w") as f:
        f.write('{"type":"FeatureCollection","features":[]}')

if __name__ == "__main__":
    update_radar()
