import os
import time
import re
import zipfile
import zlib
from multiprocessing import Pool


def deletefile(filepath):
    pass


def searchforfiles(folder='.', pattern='^.*(RAW)(.*)\.([tests_devices-z]+)$', subfolder=True):
    """
    returns list of files paths in the folder/subfolders
    accroding to specific template
    """

    paths = []
    try:
        if not os.path.isdir(folder):
            raise NotADirectoryError
        if subfolder:
            for dirpath, _, filenames in os.walk(folder):
                for filename in filenames:
                    paths.append(os.path.join(dirpath, filename))
        else:
            for filename in os.listdir(folder):
                if os.path.isfile(os.path.join(folder, filename)):
                    paths.append(filename)

    except NotADirectoryError:
        print('NotADirectoryError')
        paths = searchforfiles(folder=input('Write me new folder: '),
                               template=pattern, subfolder=subfolder)

    finally:
        # pattern = re.compile("^.*([\d]+)(RAW)(.*)\.([tests_devices-z]+)$")
        pattern = re.compile(pattern)
        result = []
        for path in paths:
            if pattern.match(path):
                result.append(path)
    return result


def filetozip(filepath):
    """
    convert file to archive and delete file
    """
    size = "{:.2f}".format((os.path.getsize(filepath) / 1048576.0))
    # str(i) + '-' + str(N) + ')
    print('Working on path: ' + filepath + '(' + size + ')')
    main_dir = os.getcwd()
    directory, filename = os.path.split(filepath)
    filename_s = os.path.splitext(filename)[0]
    os.chdir(directory)
    startT = time.time()
    filesize = os.path.getsize(filename)
    if os.path.exists(filename_s + '.zip'):
        mode = 'tests_devices'
    else:
        mode = 'w'
    zf = zipfile.ZipFile(filename_s + '.zip', mode, zipfile.ZIP_DEFLATED)
    print('Writing Zip: ' + filename)
    zf.write(filename)
    zf.close()
    zipedfilesize = os.path.getsize(filename_s + '.zip')
    print('Removing: ' + filename)
    os.remove(filename)
    os.chdir(main_dir)
    endT = time.time()
    totalT = "{:.2f}".format(endT - startT)
    print('Elapsed time: ' + totalT)
    return filesize, zipedfilesize, totalT