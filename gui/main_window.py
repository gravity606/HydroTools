import os
import json
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFileDialog, QRadioButton, 
                             QButtonGroup, QSpinBox, QMessageBox)
from PySide6.QtCore import QThread, Signal
# Importamos la función de procesamiento que guardamos en modules
from modules.rugosidad import generar_rugosidad_iber

# Hilo secundario para que ArcGIS Pro trabaje de fondo sin congelar la ventana
class HiloProcesamientoGIS(QThread):
    resultado_proceso = Signal(bool)

    def __init__(self, ruta_cobertura, ruta_dominio, tipo_cobertura, ruta_tabla_manning, resolucion, carpeta_salida):
        super().__init__()
        self.ruta_cobertura = ruta_cobertura
        self.ruta_dominio = ruta_dominio
        self.tipo_cobertura = tipo_cobertura
        self.ruta_tabla_manning = ruta_tabla_manning
        self.resolucion = resolucion
        self.carpeta_salida = carpeta_salida

    def run(self):
        # Ejecuta la función de ArcPy de forma segura en segundo plano
        exito = generar_rugosidad_iber(
            self.ruta_cobertura, 
            self.ruta_dominio, 
            self.tipo_cobertura, 
            self.ruta_tabla_manning, 
            self.resolucion, 
            self.carpeta_salida
        )
        self.resultado_proceso.emit(exito)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HydroTools v0.1 - Entorno de Trabajo")
        self.resize(500, 450)
        
        self.cargar_configuracion()
        self.ruta_proyecto_activo = None
        self.dominio_activo = None
        self.hilo_gis = None # Guardará la referencia del hilo

        self.init_ui()

    def cargar_configuracion(self):
        ruta_config = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
        with open(ruta_config, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)

        # --- GESTIÓN DE PROYECTO ---
        layout.addWidget(QLabel("<b>📁 SELECCIÓN DE PROYECTO</b>"))
        btn_proyecto = QPushButton("Abrir Proyecto (Seleccionar Carpeta)")
        btn_proyecto.clicked.connect(self.seleccionar_proyecto)
        layout.addWidget(btn_proyecto)
        
        self.lbl_proyecto = QLabel("Proyecto activo: <i>Ninguno</i>")
        layout.addWidget(self.lbl_proyecto)

        # --- RUGOSIDAD IBER (HT-001) ---
        layout.addWidget(QLabel("<br><b>🗺️ MODULO HT-001 - CREAR RUGOSIDAD IBER</b>"))
        
        layout.addWidget(QLabel("Tipo de Cobertura:"))
        self.btn_group = QButtonGroup(self)
        self.rb_siose = QRadioButton("SIOSE Normal")
        self.rb_siose_ar = QRadioButton("SIOSE AR")
        self.rb_siose.setChecked(True)
        self.btn_group.addButton(self.rb_siose)
        self.btn_group.addButton(self.rb_siose_ar)
        
        cobertura_layout = QHBoxLayout()
        cobertura_layout.addWidget(self.rb_siose)
        cobertura_layout.addWidget(self.rb_siose_ar)
        layout.addLayout(cobertura_layout)

        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolución del Raster (metros):"))
        self.sb_resolucion = QSpinBox()
        self.sb_resolucion.setRange(1, 50)
        self.sb_resolucion.setValue(1)  
        res_layout.addWidget(self.sb_resolucion)
        layout.addLayout(res_layout)

        layout.addStretch()
        self.btn_ejecutar = QPushButton("🚀 Ejecutar Proceso")
        self.btn_ejecutar.setStyleSheet("font-weight: bold; background-color: #2ca02c; color: white; padding: 10px;")
        self.btn_ejecutar.clicked.connect(self.ejecutar_rugosidad)
        layout.addWidget(self.btn_ejecutar)

    def seleccionar_proyecto(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta base del Proyecto")
        if dir_path:
            self.ruta_proyecto_activo = dir_path
            nombre_proyecto = os.path.basename(dir_path)
            self.lbl_proyecto.setText(f"Proyecto activo: <b>{nombre_proyecto}</b>")
            
            # Intenta buscar el dominio en la ruta estándar acordada
            ruta_posible_dominio = os.path.join(dir_path, "01.GIS", "00.CAPAS_BASE", "01.SHAPES", "dominio.shp")
            if os.path.exists(ruta_posible_dominio):
                self.dominio_activo = ruta_posible_dominio
                QMessageBox.information(self, "Dominio Localizado", f"Se detectó automáticamente el dominio activo:\n{ruta_posible_dominio}")
            else:
                QMessageBox.warning(self, "Dominio no encontrado", "No se encontró el archivo de dominio en la ruta de la plantilla.")
                file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Shapefile de Dominio", dir_path, "Shapefiles (*.shp)")
                if file_path:
                    self.dominio_activo = file_path

    def ejecutar_rugosidad(self):
        if not self.ruta_proyecto_activo or not self.dominio_activo:
            QMessageBox.critical(self, "Error", "Debes seleccionar primero un proyecto con un dominio activo.")
            return

        tipo = "SIOSE" if self.rb_siose.isChecked() else "SIOSE_AR"
        resolucion = self.sb_resolucion.value()
        
        # Mapeo inteligente de rutas dinámicas basadas en tu catálogo/biblioteca SIG
        if tipo == "SIOSE":
            ruta_cobertura = os.path.join(self.config["biblioteca_sig"], "SIOSE", "SIOSE_Espania.shp") 
            ruta_tabla = self.config["manning_siose_csv"]
        else:
            # En SIOSE AR pasamos la Geodatabase completa (el backend se encargará de T_COMBINADA)
            ruta_cobertura = os.path.join(self.config["biblioteca_sig"], "SIOSE_AR", "SAR2018_28_MADRID.gdb") 
            ruta_tabla = self.config["manning_siose_ar_csv"]
            
        carpeta_salida = os.path.join(self.ruta_proyecto_activo, "02.MODELIZACIONES", "00.BASE")
        
        if not os.path.exists(carpeta_salida):
            os.makedirs(carpeta_salida)

        # Desactivamos el botón para evitar que el usuario haga doble clic durante el cálculo
        self.btn_ejecutar.setEnabled(False)
        self.btn_ejecutar.setText("⏳ Procesando en ArcGIS Pro...")

        # Configuramos e iniciamos el hilo de fondo
        self.hilo_gis = HiloProcesamientoGIS(
            ruta_cobertura, self.dominio_activo, tipo, ruta_tabla, resolucion, carpeta_salida
        )
        self.hilo_gis.resultado_proceso.connect(self.proceso_finalizado)
        self.hilo_gis.start()

    def proceso_finalizado(self, exito):
        # Reactivamos la interfaz al terminar
        self.btn_ejecutar.setEnabled(True)
        self.btn_ejecutar.setText("🚀 Ejecutar Proceso")
        
        if exito:
            QMessageBox.information(self, "¡Éxito!", "Módulo HT-001: Archivo 'manning.asc' generado correctamente.")
        else:
            QMessageBox.critical(self, "Error", "El geoprocesamiento falló. Revisa la consola de ArcPy para ver el informe de errores.")
