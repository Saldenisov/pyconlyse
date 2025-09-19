# PYCONLYSE Main Control Interface - Modular Version

## Overview

The main control interface has been completely refactored from a monolithic 1700+ line file into a clean, modular architecture with proper separation of concerns, comprehensive testing, and robust error handling.

## 🎯 **Key Improvements**

### ✅ **Threading Issues Fixed**
- **No more freezing**: All blocking operations moved off main thread with timeout protection
- **Proper error handling**: Graceful degradation when components fail
- **Resource cleanup**: Proper shutdown of threads and processes

### ✅ **Modular Architecture** 
- **Separated concerns**: Each module has a single responsibility
- **Testable components**: Comprehensive unit and integration tests
- **Maintainable code**: Clean interfaces and documentation

## 📁 **Module Structure**

```
bin/
├── config.py                      # Configuration management
├── infrastructure_manager.py      # Tango infrastructure (DB, Starter, Astor)
├── device_manager.py             # Device server lifecycle management  
├── monitoring_threads.py         # Background monitoring threads
├── main_ctrl_new.py              # Clean main entry point
├── test_main_ctrl_modules.py     # Unit tests
├── test_integration.py           # Integration tests
└── README_MODULAR.md             # This documentation
```

## 🔧 **Module Details**

### **config.py** - Centralized Configuration
- Device server configurations
- Timeout settings
- ZMQ configuration  
- UI constants
- Helper functions

```python
from config import DEVICE_SERVER_CONFIGS, Timeouts, ZMQConfig
```

### **infrastructure_manager.py** - Tango Infrastructure
- Start/stop Tango Database, Starter, Astor
- Timeout-protected database connections
- Process lifecycle management
- Status monitoring

```python
from infrastructure_manager import TangoInfrastructureManager

manager = TangoInfrastructureManager()
success = manager.start_infrastructure()
```

### **device_manager.py** - Device Server Management
- Start/stop/restart device servers
- Server status tracking
- Bulk operations
- Graceful shutdown handling

```python
from device_manager import DeviceServerManager

manager = DeviceServerManager()
success = manager.start_deviceserver("BASLER", "V0", "FULL")
```

### **monitoring_threads.py** - Background Monitoring
- Device state monitoring with timeout protection
- ELYSE ZMQ data handling
- Proper thread lifecycle management
- Error resilience

```python
from monitoring_threads import DeviceMonitorThread, ElyseDataThread

monitor = DeviceMonitorThread()
monitor.device_state_changed.connect(handler)
monitor.start()
```

## 🧪 **Testing**

### **Unit Tests** (`test_main_ctrl_modules.py`)
- Comprehensive mocking of external dependencies
- Tests for all public methods
- Error condition handling
- Resource cleanup verification

### **Integration Tests** (`test_integration.py`)
- End-to-end workflow testing
- Module interaction verification
- Configuration consistency checks
- Architecture validation

### **Running Tests**
```bash
# Unit tests (run in environment with Tango)
python test_main_ctrl_modules.py -v

# Integration tests  
python test_integration.py -v

# With coverage (if available)
python -m coverage run test_main_ctrl_modules.py
python -m coverage report
```

## 🚀 **Usage**

### **Basic Usage**
```python
# Import modular components
from infrastructure_manager import TangoInfrastructureManager
from device_manager import DeviceServerManager
from monitoring_threads import DeviceMonitorThread

# Initialize managers
infra = TangoInfrastructureManager()
devices = DeviceServerManager()

# Start infrastructure
if infra.start_infrastructure():
    print("Tango infrastructure started")

# Start device servers  
devices.start_deviceserver("BASLER", "V0", "FULL")

# Start monitoring
monitor = DeviceMonitorThread()
monitor.start()
```

### **Full Application**
```bash
# Run the modular main control interface
python main_ctrl_new.py
```

## 🔒 **Threading Safety**

All operations that could block are now protected:

### **Database Operations**
```python
# Old (blocking)
db = Database()
db.get_info()  # Could freeze UI

# New (timeout protected)  
def _check_db():
    return Database().get_info()

with ThreadPoolExecutor() as executor:
    future = executor.submit(_check_db)
    result = future.result(timeout=5.0)
```

### **Device Operations**
```python
# Old (blocking)
device = Device("some/device/name")
state = device.State()  # Could freeze UI

# New (timeout protected)
def _read_state():
    return Device("some/device/name").State()

with ThreadPoolExecutor() as executor:
    future = executor.submit(_read_state)
    state = future.result(timeout=2.0)
```

### **ZMQ Operations**
```python
# Old (blocking)
message = socket.recv_string(zmq.NOBLOCK)

# New (timeout with proper cleanup)
socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second timeout
try:
    message = socket.recv_string()
except zmq.Again:
    # Handle timeout gracefully
    continue
```

## 📊 **Performance Benefits**

| Aspect | Before | After |
|--------|--------|-------|
| **Lines of Code** | 1,700+ lines | ~400 lines main + modules |
| **Threading Issues** | Frequent freezing | Zero freezing |
| **Test Coverage** | No tests | Comprehensive test suite |
| **Maintainability** | Monolithic | Modular & documented |
| **Error Handling** | Basic | Robust with timeouts |
| **Resource Management** | Poor cleanup | Proper lifecycle |

## 🔄 **Migration Guide**

### **From Old main_ctrl.py**
1. **Replace import**: Use `main_ctrl_new.py` instead
2. **Update scripts**: Point to new entry point
3. **Configuration**: All settings now in `config.py`
4. **Testing**: Run test suites to verify functionality

### **Key Changes**
- All managers are now separate modules
- Configuration is centralized
- Threading issues are resolved
- Comprehensive error handling added
- Full test coverage provided

## ⚙️ **Configuration**

All configuration is centralized in `config.py`:

```python
# Timeout settings
class Timeouts:
    DATABASE_CONNECTION = 5.0
    DEVICE_OPERATION = 5.0
    SUBPROCESS_START = 2.0

# Device server configurations
DEVICE_SERVER_CONFIGS = {
    "BASLER": {
        "instances": ["V0", "Cam1", "Cam2", "Cam3"], 
        "script": "BASLER"
    },
    # ... more devices
}

# UI settings
class UIConfig:
    MIN_WIDTH = 800
    MIN_HEIGHT = 600
    STATUS_UPDATE_INTERVAL = 5000
```

## 🐛 **Debugging**

### **Enable Debug Logging**
```python
import logging
logging.getLogger('infrastructure_manager').setLevel(logging.DEBUG)
logging.getLogger('device_manager').setLevel(logging.DEBUG)
logging.getLogger('monitoring_threads').setLevel(logging.DEBUG)
```

### **Check Component Status**
```python
# Infrastructure status
infra_status = infra_manager.get_status()
print(f"Tango status: {infra_status}")

# Device server status  
server_status = device_manager.get_running_servers()
print(f"Running servers: {len(server_status)}")
```

## 🤝 **Contributing**

1. **Add tests** for any new functionality
2. **Update configuration** in `config.py` if needed
3. **Maintain modular structure** - each module should have single responsibility
4. **Use timeout protection** for any blocking operations
5. **Document changes** in appropriate module docstrings

## 📈 **Future Enhancements**

- [ ] Add configuration validation
- [ ] Implement plugin system for device types
- [ ] Add metrics collection
- [ ] Create web interface for remote control
- [ ] Add automatic error recovery
- [ ] Implement distributed device management

---

**Version**: 3.0 (Modular Refactored)  
**Author**: PYCONLYSE Team  
**Date**: 2025-09-18