import requests
import rasterio
import os
import geopandas as gpd
from rasterio.features import shapes

BASE_URL = "https://radar-api.protezionecivile.it"

def update_radar():
    try:
        # CHIAMATA PER CUMULATA 24 ORE
        print("Richiesta ultimo timestamp per CUM24...")
        res_last = requests.get(f"{BASE_URL}/findLastProductByType?type=CUM24")
        res_last.raise_for_status()
        last_time = res_last.json()['lastProducts'][0]['time']

        print(f"Timestamp trovato: {last_time}. Richiesta URL download...")
        res_dl = requests.post(f"{BASE_URL}/downloadProduct", json={"productType": "CUM24", "productDate": last_time})
        res_dl.raise_for_status()
        download_url = res_dl.json()['url']

        tif_data = requests.get(download_url)
        with open("radar_temp.tif", "wb") as f:
            f.write(tif_data.content)

        with rasterio.open("radar_temp.tif") as src:
            image = src.read(1)
            # Soglia minima: 0.2mm nelle 24h per evitare rumore, ma catturare tutto
            mask = (image > 0.2) & (image < 255)
            
            results = ({'properties': {'mm': float(v)}, 'geometry': s} 
                       for i, (s, v) in enumerate(shapes(image, mask=mask, transform=src.transform)))
            
            df = gpd.GeoDataFrame.from_features(list(results))
            
            if not df.empty:
                df.crs = src.crs
                df = df.to_crs(epsg=4326)
                
                if not df.empty:
                df.crs = src.crs
                df = df.to_crs(epsg=4326)

                # --- OTTIMIZZAZIONE AGGRESSIVA ---
                # 1. Arrotondiamo i millimetri per raggruppare i valori simili
                df['mm'] = df['mm'].round(0).astype(int)
                
                # 2. Raggruppiamo i poligoni che hanno lo stesso valore di pioggia
                df = df.dissolve(by='mm').reset_index()

                # 3. Semplifichiamo le linee (0.01 è circa 1km di precisione)
                df['geometry'] = df['geometry'].simplify(0.01, preserve_topology=True)
                
                # 4. Rimuoviamo poligoni troppo piccoli (rumore)
                df = df[df.geometry.area > 0.001]
                # ---------------------------------

                if not os.path.exists('data'): os.makedirs('data')
                
                # Salvataggio
                df.to_file("data/pioggia_veneto.json", driver='GeoJSON')
                
                size_mb = os.path.getsize("data/pioggia_veneto.json") / (1024 * 1024)
                print(f"Successo! File ottimizzato: {size_mb:.2f} MB")
                
                if not os.path.exists('data'): os.makedirs('data')
                df.to_file("data/pioggia_veneto.json", driver='GeoJSON')
                print(f"OK! Generati {len(df)} poligoni per l'Italia (CUM24).")
            else:
                if not os.path.exists('data'): os.makedirs('data')
                with open("data/pioggia_veneto.json", "w") as f:
                    f.write('{"type":"FeatureCollection","features":[]}')
                print("Nessun dato CUM24 disponibile.")

    except Exception as e:
        print(f"Errore critico: {e}")

if __name__ == "__main__":
    update_radar()
