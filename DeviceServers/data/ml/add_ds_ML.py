from tango import Database, DbDevInfo

db = Database()

# ML device configuration - based on Jupyter notebook settings
ml_devices = {
    "ML_UV1": {
        "device_path": "ml/analysis/ML_UV1",
        "server_instance": "1_UV1",
        "ip_address": "127.0.0.1",  # ZeroMQ typically uses localhost
        "zmq_port": "5555",  # Default ZeroMQ port from notebook
        "model_path": "C:/dev/pyconlyse/DeviceServers/data/ml/models",
        "data_path": "C:/dev/spectra_raw.h5",  # From notebook analysis
        "calibration_path": "C:/dev/pyconlyse/DeviceServers/data/ml/calibrations/calibrationUV-VIS140324.txt",
        "scaler_filename": "UV1_scaler.joblib",
        "model_filename": "UV1_xgb.joblib",
    }
}

def main():
    for device_name, config in ml_devices.items():
        dev_info = DbDevInfo()
        dev_name = config["device_path"]
        dev_info.name = dev_name
        dev_info._class = "DS_ML_Stability"
        dev_info.server = f"DS_ML_Stability/{config['server_instance']}"
        
        db.add_device(dev_info)
        db.put_device_property(
            dev_name,
            {
                "ip_address": config["ip_address"],
                "zmq_port": config["zmq_port"],
                "model_path": config["model_path"],
                "scaler_filename": config["scaler_filename"],
                "model_filename": config["model_filename"],
                "data_path": config["data_path"],
                "calibration_path": config["calibration_path"],
                "friendly_name": device_name,
            },
        )
        print(f"Added ML device: {dev_name}")

if __name__ == "__main__":
    main()