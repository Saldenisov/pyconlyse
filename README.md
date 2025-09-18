# PYCONLYSE

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENCE)
[![Version](https://img.shields.io/badge/version-2.0.0-orange.svg)]()

PYCONLYSE is a comprehensive client-server-service application written in pure Python for controlling and managing scientific instruments in the ELYSE experiment. The system provides a distributed architecture using PyTango framework for device communication, data acquisition, and real-time experiment control.

## 🏗️ Architecture

PYCONLYSE follows a distributed client-server architecture with multiple components:

### Core Components

- **Tango Infrastructure**: Distributed control system infrastructure
- **Device Servers**: Hardware abstraction layer for scientific instruments
- **Client Applications**: User interfaces for device control and monitoring
- **Web Interface**: Modern React-based web frontend
- **Data Management**: HDF5-based data storage and analysis tools

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PYCONLYSE System                         │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Client Layer  │  Server Layer   │     Hardware Layer      │
│                 │                 │                         │
│ ┌─────────────┐ │ ┌─────────────┐ │ ┌─────────────────────┐ │
│ │ GUI Clients │ │ │DeviceServers│ │ │    Cameras          │ │
│ │             │ │ │             │ │ │  - ANDOR CCD        │ │
│ │ - Qt5 Apps  │ │ │ - ANDOR     │ │ │  - Basler Cameras   │ │
│ │ - Control   │ │ │ - BASLER    │ │ │  - Avantes          │ │
│ │ - Monitor   │ │ │ - AVANTES   │ │ ├─────────────────────┤ │
│ │             │ │ │ - OWIS      │ │ │    Motion Control   │ │
│ ├─────────────┤ │ │ - STANDA    │ │ │  - OWIS Stages      │ │
│ │Web Frontend │ │ │ - NETIO     │ │ │  - Standa Motors    │ │
│ │             │ │ │ - ARCHIVE   │ │ │  - TopDirect        │ │
│ │ - React App │ │ │             │ │ ├─────────────────────┤ │
│ │ - Dashboard │ │ └─────────────┘ │ │    Power Control    │ │
│ └─────────────┘ │                 │ │  - NETIO PDUs       │ │
└─────────────────┴─────────────────┴─────────────────────────┘
           ↕                ↕                    ↕
    ┌─────────────────────────────────────────────────────────┐
    │              PyTango Middleware                         │
    │  - Device Database  - Event System  - Command System   │
    └─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
pyconlyse/
├── bin/                        # Main executables and client applications
│   ├── main_ctrl.py           # Main control interface
│   ├── DS_*_client.py         # Device-specific client applications  
│   └── configure_*.py         # Configuration scripts
├── DeviceServers/             # Tango DeviceServer implementations
│   ├── base/                  # Base classes for device servers
│   ├── cameras/               # Camera control servers (ANDOR, Basler, Avantes)
│   ├── motion/                # Motion control servers (OWIS, Standa, TopDirect)
│   ├── power/                 # Power management servers (NETIO)
│   ├── control/               # Experiment control servers
│   └── data/                  # Data management servers
├── frontend/                  # React.js web interface
│   ├── src/                   # React source code
│   └── public/                # Static assets
├── web/                       # Flask backend for web interface
├── gui/                       # PyQt5 GUI components
│   ├── controllers/           # GUI controllers
│   ├── models/               # Data models
│   └── views/                # UI components
├── communication/             # Communication protocols and messaging
├── devices/                   # Hardware device interfaces
├── utilities/                 # Utility functions and tools
│   ├── data/                 # Data processing utilities
│   ├── database/             # Database utilities
│   └── logging/              # Logging configuration
├── scripts/                   # Automation and deployment scripts
└── logs_pack/                # Log management
```

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.9 or higher
- **Anaconda/Miniconda**: For environment management
- **PyTango**: Tango Controls framework
- **Node.js**: For frontend development (if modifying web interface)
- **Windows OS**: Currently optimized for Windows environments

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pyconlyse
   ```

2. **Create and activate conda environment**
   ```bash
   conda create -n pyconlyse39 python=3.9
   conda activate pyconlyse39
   ```

3. **Install Python dependencies**
   ```bash
   # Using Poetry (recommended)
   pip install poetry
   poetry install
   
   # Or using pip
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Set these environment variables (adapt paths to your system)
   set PYCONLYSE=C:\dev\pyconlyse
   set ANACONDA=C:\Users\%USERNAME%\anaconda3
   set TANGO_ROOT=C:\dev\tango_root\tango
   set PYCONLYSE_ENV=pyconlyse39
   set TANGO_HOST=localhost:10000
   ```

5. **Install Tango Controls** (if not already installed)
   - Follow [PyTango installation guide](https://pytango.readthedocs.io/en/stable/installation.html)
   - Set up Tango Database

## 🎮 Usage

### Starting the System

1. **Start Tango Infrastructure**
   ```bash
   cd bin
   # On Windows
   start_tango_improved.cmd
   # Or using PowerShell
   powershell -ExecutionPolicy Bypass -File Start-TangoInfrastructure.ps1
   ```

2. **Launch Main Control Interface**
   ```bash
   python bin/main_ctrl.py
   ```

3. **Start specific Device Servers**
   ```bash
   # Start camera server
   bin/start_deviceserver.cmd BASLER Cam1 FULL
   
   # Start motion control
   bin/start_deviceserver.cmd STANDA alignment FULL
   
   # Start power management  
   bin/start_deviceserver.cmd NETIO all FULL
   ```

### Device Control

Each device type has dedicated client applications:

```bash
# Camera control
python bin/DS_BASLER_client.py
python bin/DS_ANDOR_CCD_client.py

# Motion control  
python bin/DS_STANDA_client.py
python bin/DS_OWIS_client.py

# Power management
python bin/DS_NETIO_client.py

# Experiment control
python bin/DS_Experiment_client.py
```

### Web Interface

1. **Start the web backend**
   ```bash
   cd web
   python app.py
   ```

2. **Start the React frontend** (for development)
   ```bash
   cd frontend
   npm install
   npm start
   ```

3. **Access the interface**
   - Open browser to `http://localhost:3000`

## 🔧 Configuration

### Environment Configuration

The `.pyconlyse.config` file contains system-wide configuration:

- **Environment paths**: Conda, Tango, project directories
- **Startup scripts**: Default executables and templates
- **Version information**: System and component versions

### Device Configuration

Device servers can be configured through:

- **Tango Database**: Device properties and attributes
- **Configuration files**: Device-specific settings
- **Command line arguments**: Runtime parameters

### Logging Configuration

Logging is configured in `main_ctrl.py` and can be customized:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('main_ctrl.log'),
        logging.StreamHandler()
    ]
)
```

## 🧪 Supported Hardware

### Cameras and Imaging
- **ANDOR CCD**: Scientific CCD cameras
- **Basler Cameras**: Industrial cameras (multiple instances: Cam1, Cam2, Cam3)
- **Avantes Spectrometers**: UV-Vis spectrometers

### Motion Control
- **OWIS Positioning Systems**: Precision positioning stages
- **Standa Motors**: Stepper motor controllers with XIMC protocol
- **TopDirect Systems**: Linear actuators and positioning

### Power Management
- **NETIO PDUs**: Network-controlled power distribution units
- **GPIO Control**: Raspberry Pi GPIO interfaces

### Data Acquisition
- **Archive System**: HDF5-based data storage
- **Real-time Processing**: NumPy/SciPy-based analysis

## 🧪 Development

### Code Quality

The project uses several tools for code quality:

```bash
# Code formatting
black .
isort .

# Linting
ruff check .

# Type checking
mypy .

# Security scanning
bandit -r .

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Testing

```bash
# Run unit tests
pytest DeviceServers/testing/

# Run device-specific tests
python DeviceServers/cameras/avantes/tests/test_avantes.py
python DeviceServers/motion/standa/tests/test_standa.py
```

### Adding New Devices

1. **Create Device Server**: Implement in `DeviceServers/<category>/`
2. **Add Client Interface**: Create client in `bin/DS_<DEVICE>_client.py`
3. **Update Configuration**: Add to device configs in `main_ctrl.py`
4. **Create Startup Script**: Add device to startup templates

## 📊 Data Analysis

The project includes specialized analysis tools:

### Optical Density Analysis
```python
from Slava import calculate_optical_density_and_save

# Process HDF5 measurement files
h5_files = ('ABS.h5', 'BASE.h5', 'BRUIT.h5')
od_array, wavelengths, timedelays = calculate_optical_density_and_save(h5_files)
```

### Data Visualization
```python
# 2D spectral maps
import matplotlib.pyplot as plt
plt.imshow(od_data, aspect='auto', origin='upper')
plt.colorbar(label='Optical Density')
plt.show()
```

## 🔒 Security

- **Bandit**: Security linting for Python code
- **Environment isolation**: Conda environment separation
- **Access control**: Tango-based device access management
- **Logging**: Comprehensive audit trails

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/new-device`
3. **Make changes** and ensure tests pass
4. **Run code quality tools**: `pre-commit run --all-files`
5. **Submit a pull request**

### Development Guidelines

- Follow **PEP 8** style guidelines
- Add **type hints** for new functions
- Write **docstrings** for public APIs
- Include **unit tests** for new features
- Update **documentation** for changes

## 📋 System Requirements

### Minimum Requirements
- **OS**: Windows 10/11 (Linux support in development)
- **Python**: 3.9+
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space
- **Network**: Ethernet connection for device communication

### Recommended Setup
- **OS**: Windows 11
- **Python**: 3.9 or 3.10
- **RAM**: 16GB or more
- **Storage**: SSD with 50GB+ free space
- **GPU**: Dedicated GPU for image processing

## 📚 Documentation

- **PyTango Documentation**: [https://pytango.readthedocs.io/](https://pytango.readthedocs.io/)
- **Taurus GUI Framework**: [https://taurus-scada.org/](https://taurus-scada.org/)
- **Project Wiki**: Internal documentation and procedures
- **API Documentation**: Auto-generated from docstrings

## 🐛 Troubleshooting

### Common Issues

1. **Tango Database Connection**
   ```bash
   # Check Tango host
   echo $TANGO_HOST
   
   # Test database connection
   python -c "from tango import Database; db = Database(); print('Connected')"
   ```

2. **Device Server Startup**
   ```bash
   # Check device registration
   python -c "from tango import Database; db = Database(); print(db.get_device_list('*'))"
   ```

3. **Import Errors**
   ```bash
   # Verify environment
   conda list pytango
   pip list | grep tango
   ```

### Logging

Check log files for detailed error information:
- `main_ctrl.log`: Main application logs
- `LOG/`: Device-specific log files
- Windows Event Viewer: System-level issues

## 📄 License

This project is licensed under the MIT License - see the [LICENCE](LICENCE) file for details.

## 👥 Authors and Acknowledgments

- **PYCONLYSE Team**
- **Primary Contact**: saldenisov@gmail.com
- **Institution**: ELYSE Experiment Laboratory

### Special Thanks
- PyTango community for the distributed control framework
- Taurus project for GUI components
- Scientific Python ecosystem contributors

---

## 🔗 Related Projects

- **PyTango**: [https://github.com/tango-controls/pytango](https://github.com/tango-controls/pytango)
- **Taurus**: [https://github.com/taurus-org/taurus](https://github.com/taurus-org/taurus)
- **HDF5**: Data storage format for scientific computing

---

*For more detailed information, refer to the individual component documentation in their respective directories.*
