"""POLARIS09 Earth Engine API for Vercel Python Functions.
Requires GEE_SERVICE_ACCOUNT_JSON (full JSON secret) and registered EE project.
Never expose credentials to the browser or repository.
"""
from http.server import BaseHTTPRequestHandler
import json, os, traceback
from urllib.parse import urlparse

PROJECT = "unajma-hidrologia-peru"

def reply(handler, code, payload):
    body=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Cache-Control","no-store")
    handler.send_header("Content-Length",str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def ee_client():
    import ee
    secret=os.getenv("GEE_SERVICE_ACCOUNT_JSON","")
    if not secret:
        raise RuntimeError("Falta configurar GEE_SERVICE_ACCOUNT_JSON en Vercel. El ID de proyecto no autentica por sí solo.")
    info=json.loads(secret)
    email=info.get("client_email")
    if not email or info.get("type")!="service_account":
        raise RuntimeError("La variable GEE_SERVICE_ACCOUNT_JSON no contiene una cuenta de servicio válida.")
    creds=ee.ServiceAccountCredentials(email,key_data=secret)
    ee.Initialize(credentials=creds,project=PROJECT)
    return ee

def run(body):
    ee=ee_client()
    geo=body.get("aoi")
    if not isinstance(geo,dict):
        raise ValueError("Debes proporcionar un área de estudio GeoJSON.")
    if geo.get("type")=="FeatureCollection":
        geom=ee.FeatureCollection(geo).geometry()
    elif geo.get("type")=="Feature":
        geom=ee.Feature(geo).geometry()
    else:
        geom=ee.Geometry(geo)
    area=geom.area(maxError=100).getInfo()
    if area>5e10:
        raise ValueError("Área de estudio demasiado grande para esta API.")
    kind=body.get("kind","ndvi")
    start=body.get("start_date","2025-01-01")
    end=body.get("end_date","2025-12-31")
    cloud=min(100,max(0,int(body.get("max_cloud_percent",20))))
    if kind in ("ndvi","ndwi","evi","savi","ndre","mndwi"):
        collection=(ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom).filterDate(start,end)
            .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE",cloud)))
        count=collection.size().getInfo()
        if not count:
            return {"status":"no_data","message":"No hay imágenes Sentinel-2 en el intervalo y nubosidad elegidos.","count":0}
        image=collection.median().multiply(.0001)
        if kind=="ndvi": idx=image.normalizedDifference(["B8","B4"]).rename("NDVI")
        elif kind=="ndwi": idx=image.normalizedDifference(["B3","B8"]).rename("NDWI")
        elif kind=="mndwi": idx=image.normalizedDifference(["B3","B11"]).rename("MNDWI")
        elif kind=="ndre": idx=image.normalizedDifference(["B8","B5"]).rename("NDRE")
        elif kind=="evi": idx=image.expression("2.5*(n-r)/(n+6*r-7.5*b+1)",{"n":image.select("B8"),"r":image.select("B4"),"b":image.select("B2")}).rename("EVI")
        else: idx=image.expression("1.5*(n-r)/(n+r+0.5)",{"n":image.select("B8"),"r":image.select("B4")}).rename("SAVI")
        vis={"min":-1,"max":1,"palette":["#7f3b08","#f7f7f7","#1a9850"]}
        tile=idx.clip(geom).getMapId(vis)["tile_fetcher"].url_format
        stats=idx.reduceRegion(reducer=ee.Reducer.mean(),geometry=geom,scale=30,maxPixels=10000000,bestEffort=True).getInfo()
        return {"status":"ok","source":"COPERNICUS/S2_SR_HARMONIZED","project":PROJECT,"kind":kind,"image_count":count,"statistics":stats,"tile_url":tile,"legend":vis,"area_ha":round(area/10000,2),"note":"Composición mediana sin máscara QA60/SCL avanzada. Resultados preliminares, sujetos a validación."}
    if kind=="landcover":
        image=ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
        vis={"min":10,"max":100,"palette":["#006400","#ffbb22","#ffff4c","#f096ff","#fa0000","#b4b4b4","#f0f0f0","#0064c8","#0096a0","#00cf75","#fae6a0"]}
        tile=image.clip(geom).getMapId(vis)["tile_fetcher"].url_format
        return {"status":"ok","source":"ESA/WorldCover/v200","project":PROJECT,"kind":kind,"tile_url":tile,"area_ha":round(area/10000,2),"note":"Clasificación WorldCover 2021. No se han calculado porcentajes por clase."}
    raise ValueError("Análisis no implementado en el motor GEE: "+str(kind))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path!="/api/gee":
            return reply(self,404,{"error":"Ruta no encontrada"})
        return reply(self,200,{"status":"configured" if os.getenv("GEE_SERVICE_ACCOUNT_JSON") else "credentials_required","project":PROJECT,"message":"La autenticación del proyecto depende de la cuenta de servicio autorizada."})
    def do_POST(self):
        if urlparse(self.path).path!="/api/gee":
            return reply(self,404,{"error":"Ruta no encontrada"})
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<=0 or n>1000000: return reply(self,413,{"error":"GeoJSON vacío o mayor de 1 MB"})
            body=json.loads(self.rfile.read(n))
            result=run(body)
            return reply(self,200,result)
        except ValueError as ex:
            return reply(self,400,{"error":str(ex)})
        except Exception as ex:
            return reply(self,503,{"error":str(ex),"project":PROJECT})
