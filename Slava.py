import numpy as np
from tqdm import tqdm
from pathlib import Path
import h5py
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

def calculate_optical_density_and_save(h5_files_tuple):
    """
    Calculate the optical density (OD) for each N using the provided HDF5 files,
    attach wavelengths as the 0th column, timedelays as the 0th row, and save
    each OD_n as `n.dat` in the parent directory of the ABS file.

    Parameters:
        h5_files_tuple (tuple): Tuple of three HDF5 file paths (ABS, BASE, BRUIT).

    Returns:
        tuple: (od_array, wavelengths, timedelays)
            - od_array: numpy array of calculated OD values for each N.
            - wavelengths: array of wavelengths.
            - timedelays: array of time delays.
    """
    abs_file, base_file, bruit_file = h5_files_tuple

    # Load raw_data, wavelengths, and timedelays from each file
    with h5py.File(Path(abs_file), 'r') as abs_h5, \
         h5py.File(Path(base_file), 'r') as base_h5, \
         h5py.File(Path(bruit_file), 'r') as bruit_h5:
        abs_raw_data = abs_h5['raw_data'][:]
        base_raw_data = base_h5['raw_data'][:]
        bruit_raw_data = bruit_h5['raw_data'][:]
        wavelengths = abs_h5['wavelengths'][:]
        timedelays = abs_h5['timedelays'][:]

        # Calculate the bruit mean
        bruit_mean = np.mean(bruit_raw_data, axis=0)

        # Validate the dimensions
        assert abs_raw_data.shape == base_raw_data.shape, \
            "Mismatch in raw_data dimensions across files."

        # Parent folder of the ABS file
        save_folder = Path(abs_file).parent

        # Calculate OD for each N
        od_array = []
        for n in range(abs_raw_data.shape[0]):
            base_n = base_raw_data[n]
            abs_n = abs_raw_data[n]

            # Prevent division by zero and invalid values
            with np.errstate(divide='ignore', invalid='ignore'):
                od_n = np.log((base_n - bruit_mean) / (abs_n - bruit_mean))
                od_n = np.nan_to_num(od_n, nan=0.0, posinf=0.0, neginf=0.0)

            # Transpose od_n to align with expected dimensions:
            # rows: wavelengths, columns: time delays.
            od_n = od_n.T
            od_array.append(od_n)

            result = np.zeros((od_n.shape[0] + 1, od_n.shape[1] + 1))
            result[1:, 1:] = od_n
            result[0, 1:] = timedelays
            result[1:, 0] = wavelengths
            result[0, 0] = 0  # First element set to zero

            save_path = save_folder / f"{n}.dat"
            #np.savetxt(save_path, result, fmt='%.6e')


    return (np.array(od_array), wavelengths, timedelays)


if __name__ == '__main__':
    # Define file paths
    p1 = Path(r'E:\ICP_notebooks\20250310_Azo\11124-cis-GdAzo_55uM_N3_5mM_N2O_400_1us-x5 5Hz')
    p0 = Path(r'E:\ICP_notebooks\20250310_Azo\11126-cis-GdAzo_55uM_N3_5mM_N2O_400_1us-x5 1Hz 100p')

    h5_files1 = (p1 / 'ABS11124.h5', p1 / 'BASE11124.h5', p0 / 'BRUIT11126.h5')
    files = [h5_files1]

    # Process each file set
    results = []
    for fileset in tqdm(files):
        results.append(calculate_optical_density_and_save(fileset))

    # Plot kinetics (mean OD for wavelengths 350-370 nm over time)
    plt.figure(figsize=(8, 6))
    for fs_idx, (od_maps, wavelengths, timedelays) in enumerate(results):
        # Process the OD maps in groups of 10 (i.e. average kinetics over 10 maps)
        for map_idx in range(0, od_maps.shape[0], 10):
            group_kinetics = []
            # Loop over the next 10 maps (or fewer if at the end)
            for j in range(map_idx, min(map_idx + 10, od_maps.shape[0])):
                # Create a mask for wavelengths between 350 and 390 nm.
                wave_mask = (wavelengths >= 350) & (wavelengths <= 390)
                if np.any(wave_mask):
                    # Compute kinetics: average over the selected wavelengths for each time delay.
                    kinetics = np.mean(od_maps[j][wave_mask, :], axis=0)
                    group_kinetics.append(kinetics)
            # Average the kinetics curves from this group (if any)
            if group_kinetics:
                avg_kinetics = np.mean(group_kinetics, axis=0)
                # Only plot if the maximum averaged kinetics is less than or equal to 0.2.
                if np.max(avg_kinetics) <= 0.2:
                    plt.plot(timedelays, avg_kinetics, label=f'{map_idx}_average')
                    plt.ylim(0, 0.3)

    plt.xlabel('Time Delays')
    plt.ylabel('Mean Optical Density (350-370 nm)')
    plt.title('Kinetics (OD) for Wavelengths 350-370 nm')
    plt.legend(fontsize='small')
    plt.grid(True)
    plt.show()
