import sys
from pathlib import Path
from typing import Optional

app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from gui.DS_General_Client import main
from DeviceServers.data.ml.DS_ML_Widget import ML_Stability
from gui.Panels import GeneralPanel

# Device layouts for ML stability devices
layouts = {
    "ML_UV1": {
        "selection": ["ml/analysis/ML_UV1"],
        "width": 1,
    },
    "all": {
        "selection": [
            "ml/analysis/ML_UV1",
        ],
        "width": 1,
    },
}


def start_ml_client(instance: Optional[str] = None, vis_type=None, standalone=True):
    """Start ML Stability client programmatically
    
    Args:
        instance: Device selection ('ML_UV1', 'all')
        vis_type: Visualization type (VisType enum or None for FULL)
        standalone: Whether to run as standalone application
        
    Returns:
        Panel instance if not standalone, None otherwise
    """
    from DeviceServers.shared.DS_Widget import VisType
    
    if vis_type is None:
        vis_type = VisType.FULL
    
    return main(
        GeneralPanel, 
        "ML Stability", 
        ML_Stability, 
        "bin/icons/ML.ico",  # Create this icon or use existing one
        layouts, 
        instance=instance, 
        vis_type=vis_type, 
        standalone=standalone
    )


if __name__ == "__main__":
    main(GeneralPanel, "ML Stability", ML_Stability, "bin/icons/ML.ico", layouts)
