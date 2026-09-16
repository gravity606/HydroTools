import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    # Inicializar la aplicación de Qt
    app = QApplication(sys.argv)
    
    # Crear y mostrar la ventana principal
    window = MainWindow()
    window.show()
    
    # Arrancar el bucle de eventos
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
