import numpy as np
from tqdm import tqdm
from pathlib import Path
import h5py
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

# Read the file "20.dat" using NumPy
data = np.loadtxt(r'E:\ICP_notebooks\20250310_Azo\11121-water_600_1us-x0\2.dat')


# Exclude the first row and the first column and transpose if needed
data_to_plot = data[1:, 1:]

# Plot the data using imshow
plt.figure(figsize=(8, 6))
plt.imshow(data_to_plot, aspect='auto', origin='upper', vmin=0, vmax=0.3)
plt.colorbar(label='Optical Density')
plt.title('OD Map from 20.dat (Excluding First Row & Column)')
plt.xlabel('Time Delay Index')
plt.ylabel('Wavelength Index')
plt.show()

