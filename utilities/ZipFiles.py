"""
Run all document tex files in the folder
"""

import os
import re
import time
import zipfile
from multiprocessing import Pool


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
        #pattern = re.compile("^.*([\d]+)(RAW)(.*)\.([tests_devices-z]+)$")
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
    #str(i) + '-' + str(N) + ')
    print('Working on path: ' + filepath + '(' + size + ')')
    main_dir = os.getcwd()
    directory, filename = os.path.split(filepath)
    filename_s = os.path.splitext(filename)[0]
    os.chdir(directory)
    startT = time.time()
    filesize = os.path.getsize(filename)
    if os.path.exists(filename_s+'.zip'):
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


def userresponse(question):
    s = input(question)
    if s.lower() == 'y':
        run = True
        return run
    elif s.lower() == 'n':
        run = False
        return run
    else:
        print('Did not get you')
        userresponse('Yes or No. Type: y/n')

def doitmultiproc(paths):   
        pool = Pool(6)
        results = pool.map(filetozip, paths)
        pool.close()
        pool.join()
        return results
    
async def doitacyns(paths):
        pool = Pool(6)
        results = pool.map(filetozip, paths)
        return results

def runit(folder='.', pattern='^.*(.*)\.(raw)$', subfolder=True):
    paths = searchforfiles(folder=folder, pattern=pattern, subfolder=subfolder)
    i = 0
    N = len(paths)
    print("I'm starting zipping files" + pattern + " in folder: " + folder)

    q = 'Are you sure you want to do it. There will be no way back. Type (y/n): '
    run = userresponse(q)
    oldsize = 0
    newsize = 0
    totalT = 0
    if run:
        startT = time.time()
        results = doitmultiproc(paths)
        for res in results:
            oldsize += res[0]
            newsize += res[1]
        oldsize = "{:.2f}".format((oldsize / 1048576.0))
        newsize = "{:.2f}".format((newsize / 1048576.0))
        print('Num of files:  ' + str(N) + ' were compressed from:')
        print(str(oldsize) + ' to ' + str(newsize) + 'Mb')
        endT = time.time()
        totalT = endT - startT
        print('Total time: ' + "{:.2f}".format(totalT / 60.) + ' min')

if __name__ == '__main__':
    runit()
    input('Press Enter to leave me alone')
