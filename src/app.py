from PyQt6.QtWidgets import QApplication, QStyleFactory
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor
import sys
import os

from .widgets.explorer import EExplorer

def setup_application_style(app: QApplication):
    """Configure application-wide styling"""
    # Force system theme integration
    app.setStyle('Fusion')
    
    # Detect desktop environment
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    
    # Apply theme based on desktop environment
    if 'cinnamon' in desktop:
        try:
            import subprocess
            result = subprocess.run(
                ['gsettings', 'get', 'org.cinnamon.desktop.interface', 'gtk-theme'],
                capture_output=True,
                text=True
            )
            if 'dark' in result.stdout.lower():
                app.setStyle('Fusion')
                palette = app.palette()
                palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
                palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
                app.setPalette(palette)
        except:
            pass

    try:
        # Apply dark theme if available
        if hasattr(QStyleFactory, 'keys') and "Fusion" in QStyleFactory.keys():
            app.setStyle("Fusion")
            # Set dark palette
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            app.setPalette(palette)
    except Exception as e:
        print(f"Could not apply dark theme: {e}")
        pass

def main():
    app = QApplication(sys.argv)
    setup_application_style(app)
    
    window = EExplorer()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 