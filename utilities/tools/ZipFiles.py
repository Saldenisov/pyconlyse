"""
Run all document tex files in the folder
"""

import time
from multiprocessing import Pool
from utilities.tools.filesfunc import searchforfiles, filetozip


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


def runit(folder='.', pattern='^.*(.*)\.(raw)$', subfolder=True):
    paths = searchforfiles(folder=folder, pattern=pattern, subfolder=subfolder)
    i = 0
    N = len(paths)
    print("I'm starting zipping files" + pattern + " in folder: " + folder)
    print('N: {}'.format(N))
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
