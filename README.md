# Pyconlyse
## The experimentation control software on the [ELYSE platform](https://www.icp.universite-paris-saclay.fr/plateformes/elyse/)

[![Build Status](https://travis-ci.org/joemccann/dillinger.svg?branch=master)](https://travis-ci.org/joemccann/dillinger)

**PYCONLYSE** is client-server-service software written in pure Python (3.8, 64 bit) using [TANGO](https://www.tango-controls.org/) scada for controlling experiments on the [ELYSE platform](https://www.icp.universite-paris-saclay.fr/plateformes/elyse/), [CNRS ICP](https://www.icp.universite-paris-saclay.fr/), France.

- For Windows OS only:( not all instruments support Linux
- Device servers are written in pure Python 3.8, 64 bit, based on DLLs provided by manufacturers
- all GUIs are based [TAURUS](https://tango-controls.readthedocs.io/en/latest/tools-and-extensions/gui/taurus/index.html) API
- Works in a bundle with LabVIEW based control-sofrware for experimental manipulation TRANCON
- Archiving data, based on [hdf5](https://www.hdfgroup.org/solutions/hdf5/) library


## Basic instumentation
- Stepmotors and actuators: 
-- [OWIS](https://www.owis.eu/), [Standa](https://www.standa.lt/),  homemade controllers
- CCD devices:
-- [ANDOR](https://andor.oxinst.com/products/ccd-cameras), [AVANTES](https://www.avantes.com/), [BASLER](https://www.baslerweb.com/en/), [Stresing](http://www.stresing.de/)
- PID
- RPI3 and RPI4 GPIO control
- PDU
-- [NETIO](https://www.netio-products.com/)


