from PyQt6.QtGui import QColor

class AppColors:
    """
    Standard palette for the application to ensure consistent tones 
    across light and dark themes.
    Based on Material Design 500 series which offers good visibility 
    on both light and dark backgrounds.
    """
    
    # Primary Palette (Material 500)
    PRIMARY = "#2196f3"    # Blue
    SUCCESS = "#4caf50"    # Green
    WARNING = "#ff9800"    # Orange
    DANGER = "#f44336"     # Red
    
    # Additional Tones
    TEAL = "#009688"       # Teal
    GREY = "#9e9e9e"       # Grey
    
    # Stylesheet Helpers
    @staticmethod
    def danger_style() -> str:
        return f"color: {AppColors.DANGER}; font-weight: bold;"
        
    @staticmethod
    def warning_style() -> str:
        return f"color: {AppColors.WARNING}; font-weight: bold;"
        
    @staticmethod
    def success_style() -> str:
        return f"color: {AppColors.SUCCESS}; font-weight: bold;"
        
    @staticmethod
    def danger_button_style() -> str:
        return f"background-color: {AppColors.DANGER}; color: white; font-weight: bold; border-radius: 4px; padding: 5px;"
