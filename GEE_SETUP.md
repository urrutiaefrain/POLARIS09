# POLARIS09 · Earth Engine

Proyecto: `unajma-hidrologia-peru`.

1. Habilitar Earth Engine API en Google Cloud para el proyecto.
2. Registrar el proyecto para uso de Earth Engine y conceder acceso a la identidad de servicio.
3. Crear una cuenta de servicio con permisos mínimos adecuados para Earth Engine.
4. Configurar en Vercel **Environment Variables**: `GEE_SERVICE_ACCOUNT_JSON` con el contenido JSON completo de la clave. **Nunca subirlo a GitHub ni pegarlo en el navegador**.
5. Volver a desplegar y consultar `/api/gee`; el estado deberá cambiar de `credentials_required` a `configured`.
6. Seleccionar un AOI y ejecutar NDVI, NDWI, EVI, SAVI, NDRE, MNDWI o WorldCover.

Las consultas a Earth Engine pueden exceder el tiempo de ejecución de Vercel; para producción y tareas pesadas usar un worker persistente con cola de trabajos.
