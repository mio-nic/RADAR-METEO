import requests
import rasterio
import os
import geopandas as gpd
from rasterio.features import shapes
from shapely.geometry import shape

BASE_URL = "https://radar-api.protezionecivile.it"

def update_radar():
    try:
        # 1. Recupero timestamp
        res_last = requests.get(f"{BASE_URL}/findLastProductByType?type=CUM24", timeout=30)
        res_last.raise_for_status()
        last_time = res_last.json()['lastProducts'][0]['time']

        # 2. Download URL
        res_dl = requests.post(f"{BASE_URL}/downloadProduct", 
                               json={"productType": "CUM24", "productDate": last_time},
                               timeout=30)
        res_dl.raise_for_status()
        download_url = res_dl.json().get('url')

        # 3. Download file
        tif_data = requests.get(download_url, timeout=60)
        with open("radar_temp.tif", "wb") as f:
            f.write(tif_data.content)

        # 4. Elaborazione GIS Avanzata
        with rasterio.open("radar_temp.tif") as src:
            image = src.read(1)
            # Prendiamo tutti i dati validi
            mask = (image > 0.5) & (image < 200)
            
            # Estraiamo le "shapes" direttamente come oggetti Shapely
            results = [
                {'properties': {'mm': float(v)}, 'geometry': shape(s)} 
                for s, v in shapes(image, mask=mask, transform=src.transform)
            ]
            
            df = gpd.GeoDataFrame.from_features(results)
            
            if not df.empty:
                df.crs = src.crs
                df = df.to_crs(epsg=4326)
                
                # RITAGLIO VENETO
                df = df.cx[10.5:13.1, 44.7:46.7]

                if not df.empty:
                    # --- SOLUZIONE SPAZI VUOTI ---
                    # 1. Raggruppiamo la pioggia in classi più ampie per "saldare" i pixel
                    # (es. 1.2 e 1.4 diventano entrambi 1)
                    df['mm'] = df['mm'].round(0).astype(int)
                    
                    # 2. Dissolve: fonde i poligoni adiacenti con lo stesso valore
                    df = df.dissolve(by='mm').reset_index()

                    # 3. BUFFER POSITIVO E NEGATIVO (Cruciale)
                    # Usiamo un buffer leggermente più grande (0.0015) per forzare la chiusura dei pixel
                    df['geometry'] = df['geometry'].buffer(0.0015, join_style=1).buffer(-0.0015, join_style=1)

                    # 4. Semplificazione finale
                    df['geometry'] = df['geometry'].simplify(0.0005, preserve_topology=True)
                    
                    if not os.path.exists('data'): os.makedirs('data')
                    df.to_file("data/pioggia_veneto.json", driver='GeoJSON')
                    print("Mappa salvata senza spazi vuoti.")
                else:
                    crea_file_vuoto()
            else:
                crea_file_vuoto()

    except Exception as e:
        print(f"ERRORE: {str(e)}")

def crea_file_vuoto():
    if not os.path.exists('data'): os.makedirs('data')
    with open("data/pioggia_veneto.json", "w") as f:
        f.write('{"type":"FeatureCollection","features":[]}')

if __name__ == "__main__":
    update_radar()
