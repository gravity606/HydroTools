import os
import arcpy

# Asegurar que las herramientas de Spatial Analyst estén disponibles
arcpy.CheckOutExtension("Spatial")

def generar_rugosidad_iber(ruta_cobertura, ruta_dominio, tipo_cobertura, ruta_tabla_manning, resolucion, carpeta_salida):
    """
    Backend para el módulo HT-001: Procesamiento geométrico y rasterización de rugosidades.
    """
    # Configurar el entorno de ArcPy utilizando el Dominio Activo como extensión
    arcpy.env.overwriteOutput = True
    arcpy.env.extent = arcpy.Describe(ruta_dominio).extent
    
    # 1. Definir nombres de campos según el tipo de cobertura elegida
    if tipo_cobertura.upper() == "SIOSE":
        campo_clasificacion = "CODIIGE"
    elif tipo_cobertura.upper() == "SIOSE_AR":
        campo_clasificacion = "ID_COBERTURA_MAX"
        # Si es un .gdb de SIOSE AR, apuntar directamente al Feature Class interno T_COMBINADA
        if ruta_cobertura.endswith(".gdb"):
            ruta_cobertura = os.path.join(ruta_cobertura, "T_COMBINADA")
    else:
        raise ValueError("Tipo de cobertura no soportado. Debe ser SIOSE o SIOSE_AR.")

    # Rutas temporales en memoria para agilizar el procesamiento
    capa_clip = "in_memory/capa_clip"
    capa_dissolve1 = "in_memory/capa_dissolve1"
    capa_dissolve2 = "in_memory/capa_dissolve2"
    raster_salida = os.path.join(carpeta_salida, "manning_temp.tif")
    ascii_salida = os.path.join(carpeta_salida, "manning.asc")

    try:
        # Paso 3: Recorte (Clip) con el Dominio Activo
        arcpy.analysis.Clip(
            in_features=ruta_cobertura, 
            clip_features=ruta_dominio, 
            out_feature_class=capa_clip
        )

        # Paso 4: Primer Dissolve por el código de ocupación del suelo
        arcpy.management.Dissolve(
            in_features=capa_clip, 
            out_feature_class=capa_dissolve1, 
            dissolve_field=campo_clasificacion
        )

        # Paso 6: Crear el campo Manning (Double) y hacer la unión de datos (Join)
        arcpy.management.AddField(
            in_table=capa_dissolve1, 
            field_name="Manning", 
            field_type="DOUBLE"
        )
        
        # Join automático con el archivo CSV de equivalencias
        arcpy.management.JoinField(
            in_data=capa_dissolve1, 
            in_field=campo_clasificacion, 
            join_table=ruta_tabla_manning, 
            join_field=campo_clasificacion, 
            fields=["Manning"] # Asume que el CSV tiene una columna llamada Manning
        )

        # Paso 7: Segundo Dissolve agrupando por el valor de rugosidad de Manning obtenido
        arcpy.management.Dissolve(
            in_features=capa_dissolve1, 
            out_feature_class=capa_dissolve2, 
            dissolve_field="Manning"
        )

        # Paso 8: Crear ID consecutivo ordenando de menor a mayor rugosidad
        arcpy.management.AddField(
            in_table=capa_dissolve2, 
            field_name="ID", 
            field_type="LONG"
        )
        
        # Cursor para asignar IDs secuenciales numéricos (1, 2, 3...) según el orden de Manning
        with arcpy.da.UpdateCursor(capa_dissolve2, ["ID", "Manning"], sql_clause=(None, "ORDER BY Manning ASC")) as cursor:
            id_consecutivo = 1
            for row in cursor:
                row[0] = id_consecutivo
                cursor.updateRow(row)
                id_consecutivo += 1

        # Paso 9: Polygon to Raster usando el ID creado como valor de celda
        arcpy.conversion.PolygonToRaster(
            in_features=capa_dissolve2, 
            value_field="ID", 
            out_raster=raster_salida, 
            cell_assignment="CELL_CENTER", 
            cellsize=resolucion
        )

        # Paso 10: Raster to ASCII (Genera el archivo .asc final requerido por IBER)
        arcpy.conversion.RasterToASCII(
            in_raster=raster_salida, 
            out_ascii_file=ascii_salida
        )

        # Limpieza de archivos raster intermedios en el disco
        if arcpy.Exists(raster_salida):
            arcpy.management.Delete(raster_salida)
            
        print("Procesamiento GIS completado. Archivo manning.asc generado.")
        return True

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        return False
    finally:
        # Liberar la memoria temporal de ArcGIS
        arcpy.management.Delete("in_memory")