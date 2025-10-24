# PYCONLYSE Web Server - Production Deployment Guide

## Overview

The PYCONLYSE web application uses Flask with Socket.IO for real-time communication. For production deployment, you must use a proper WSGI server with WebSocket support.

## Production vs Development

### Development Mode (`start_pyconlyse_server.py`)
- ✅ Auto-reload on code changes
- ✅ Detailed error messages
- ⚠️ **NOT suitable for production**
- Uses Flask development server with `debug=True`
- **Port:** 5001
- **URL:** http://10.20.30.202:5001

### Production Mode (`start_production.py`)
- ✅ Optimized performance
- ✅ Proper WebSocket support via eventlet
- ✅ No auto-reload (stability)
- ✅ `debug=False` for security
- ✅ Suitable for production deployment
- **Port:** 5000
- **URL:** http://10.20.30.202:5000
- **Auto-starts:** Via `tango_windows_startup.ps1` on everest host

## Quick Start - Production

### 1. Install Production Dependencies

```powershell
pip install eventlet
```

**Why eventlet?** Flask-SocketIO requires either `eventlet` or `gevent` for proper WebSocket support. On Windows, `eventlet` is the recommended choice.

### 2. Set Environment Variables (Optional but Recommended)

```powershell
# Set a secure JWT secret key
$env:JWT_SECRET_KEY = "your-secure-random-key-here-change-this"
```

### 3. Build React Frontend (if applicable)

```powershell
cd frontend
npm run build
cd ..
```

### 4. Start Production Server

```powershell
python start_production.py
```

The server will start at: `http://10.20.30.202:5000`

**Note:** On the `everest` host, the production server starts automatically via `C:\dev\pyconlyse\bin\windows_startup\tango_windows_startup.ps1`

## Production Configuration Checklist

### Security
- [ ] Change JWT secret key (set `JWT_SECRET_KEY` environment variable)
- [ ] Enable HTTPS if possible
- [ ] Set `JWT_COOKIE_SECURE = True` in `backend/app.py` (requires HTTPS)
- [ ] Consider enabling CSRF protection (`JWT_COOKIE_CSRF_PROTECT = True`)
- [ ] Review CORS settings in `backend/app.py`

### Performance
- [ ] Build React frontend for production (`npm run build`)
- [ ] Set `debug=False` ✅ (already configured in `start_production.py`)
- [ ] Disable auto-reloader ✅ (already configured)
- [ ] Monitor server resources (CPU, memory, network)

### Monitoring
- [ ] Set up logging to files
- [ ] Configure log rotation
- [ ] Monitor WebSocket connections
- [ ] Set up health check endpoints
- [ ] Monitor Tango device connections

## WebSocket Support

The application uses Socket.IO for real-time communication with device servers. Socket.IO provides:

- **Automatic reconnection** if connection is lost
- **Fallback to HTTP long-polling** if WebSocket fails
- **Bidirectional communication** between client and server

### Why eventlet?

Flask-SocketIO supports several async modes:
- **eventlet** ✅ Recommended for Windows
- **gevent** (alternative for Unix systems)
- **threading** ⚠️ Limited WebSocket support

Without eventlet/gevent, Socket.IO falls back to threading mode, which has limitations with WebSocket connections.

## Advanced Deployment Options

### Option 1: Direct Production (Current Setup)
```powershell
python start_production.py
```

**Pros:**
- Simple setup
- Built-in WebSocket support
- Good for internal network deployment

**Cons:**
- Single process (no load balancing)
- No automatic restart on crash

### Option 2: Windows Service
Use `pywin32` or `NSSM` to run as a Windows service:

```powershell
# Using NSSM (Non-Sucking Service Manager)
nssm install PyconlyseWeb "C:\path\to\python.exe" "C:\dev\pyconlyse\web\start_production.py"
nssm start PyconlyseWeb
```

### Option 3: Reverse Proxy (nginx/Apache)
For production with HTTPS and load balancing:

```nginx
server {
    listen 443 ssl;
    server_name pyconlyse.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://10.20.30.202:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /socket.io {
        proxy_pass http://10.20.30.202:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Option 4: Docker Deployment
Create a `Dockerfile` for containerized deployment (future option).

## Troubleshooting

### Issue: WebSocket connection fails

**Solution:** Ensure `eventlet` is installed:
```powershell
pip install eventlet
```

### Issue: "Address already in use"

**Solution:** Check if port 5000 is occupied:
```powershell
netstat -ano | findstr :5000
```

Kill the process or change the port in `start_production.py`.

### Issue: Cannot connect from other machines

**Solution:**
1. Check Windows Firewall settings
2. Verify the IP address `10.20.30.202` is correct
3. Ensure the network allows connections to port 5000

### Issue: Tango device connection errors

**Solution:**
1. Verify Tango database is running
2. Check `TANGO_HOST` environment variable
3. Ensure device servers are registered and running

## Monitoring and Logs

### View Server Logs
The server outputs to stdout. For persistent logging:

```python
# Add to start_production.py
import logging
logging.basicConfig(
    filename='pyconlyse_production.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Monitor Active Connections
Access the Socket.IO admin UI (if configured) or check logs for connection events.

## Performance Tuning

### Increase Worker Threads (if needed)
The default `eventlet` configuration should handle multiple concurrent connections. If you need more performance:

```python
# In start_production.py, you can tune eventlet:
import eventlet
eventlet.monkey_patch()  # Patch standard library for async
```

### Connection Limits
Monitor the number of concurrent WebSocket connections based on your hardware:
- **1GB RAM**: ~500-1000 connections
- **4GB RAM**: ~2000-5000 connections
- **8GB+ RAM**: Higher capacity

## Security Considerations

1. **JWT Secret Key:** Always use a strong, random secret key in production
2. **HTTPS:** Enable HTTPS for production deployments (required for `JWT_COOKIE_SECURE`)
3. **CORS:** Review and restrict CORS origins in `backend/app.py`
4. **Input Validation:** Ensure all API endpoints validate input
5. **Rate Limiting:** Consider adding rate limiting to prevent abuse
6. **Firewall:** Restrict access to port 5000 to trusted networks only

## Backup and Recovery

1. **Regular backups** of configuration files
2. **Document** any custom device configurations
3. **Test** disaster recovery procedures
4. **Version control** all configuration changes

## Support

For issues or questions:
- Email: saldenisov@gmail.com
- Check logs in `pyconlyse_production.log`
- Review Tango device server logs

---

**Last Updated:** 2025-10-23
**Version:** 2.0.0
