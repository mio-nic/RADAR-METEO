import requests
import rasterio
import os
import geopandas as gpd
from rasterio.features import shapes
from shapely.geometry import shape

BASE_URL = "https://radar-api.protezionecivile.it"

def update_radar():
    try:
        res_last = requests.get(f"{BASE_URL}/findLastProductByType?type=CUM24", timeout=30)
        res_last.raise_for_status()
        last_time = res_last.json()['lastProducts'][0]['time']

        res_dl = requests.post(f"{BASE_URL}/downloadProduct", json={"productType": "CUM24", "productDate": last_time})
        download_url = res_dl.json().get('url')
        tif_data = requests.get(download_url)
        with open("radar_temp.tif", "wb") as f:
            f.write(tif_data.content)

        with rasterio.open("radar_temp.tif") as src:
            image = src.read(1)
            mask = (image > 0.2) & (image < 200)
            results = [{'properties': {'mm': float(v)}, 'geometry': shape(s)} for s, v in shapes(image, mask=mask, transform=src.transform)]
            df = gpd.GeoDataFrame.from_features(results)
            
            if not df.empty:
                df.crs = src.crs
                df = df.to_crs(epsg=4326)
                df = df.cx[10.5:13.1, 44.7:46.7]

                if not df.empty:
                    # --- QUESTE RIGHE ORA SONO INDENTATE CORRETTAMENTE ---
                    df['mm'] = (df['mm'] * 5).round().astype(float) / 5
                    df = df.dissolve(by='mm').reset_index()
                    df['geometry'] = df['geometry'].simplify(0.0001, preserve_topology=True)
                    
                    if not os.path.exists('data'): os.makedirs('data')
                    df.to_file("data/pioggia_veneto.json", driver='GeoJSON')
                    print("Aggiornamento completato.")
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    update_radar()
