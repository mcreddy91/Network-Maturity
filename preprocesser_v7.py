# -*- coding: utf-8 -*-
"""
Created on Thu Mar 29 17:08:02 2012

@author: sebastian
"""

# third attempt at getting something to run that actually already worked

# first of all, get the imports done
import os
import numpy as np
import nibabel as nib
import sys
from multiprocessing import Pool


"""
we need a Loader, a HeadGrabber, a Masker and an Averager (possibly this
could also be done by the Masker)
lastly, we need a main(): to call the whole shebang
should need to use consistent variable names

Todo:
    - put dir-exists checks into TexSaver and NifSaver!

    - think about a better way to resetting the variables at the end of loops

    - think about a solution for dataset structures where there is no relative
    path for the functional files (i.e. the functional lies directly in the
    subject directory)

    - all variables in camelcase, all functions with capital first letter

    - print # of current subject with total # of subjects next to it
      (i.e. Running subject 10 of 100)

    - think about whether the flexibility of the script should be tailored
      towards the filenames of batchfile.txt and configfile.txt, towards the
      path where these are located or both. Right now we have flexible
      filenames and inflexible paths (though we also have flexible paths if
      called through import)

v1 3/5/12:
    implemented the rough stuff
v2 3/8/12:
    changes include the ability to run multiple files given by a textfile
v3 3/9/12:
    correlationmatrix
v4 3/12/12:
    support vector machine and cleaning up of the code
v5 3/16/12:
    remove svm again (doesn't make sense in this module) and prepare code for
    running separately for different subjects
v6 3/19/12:
    implement parallelization, cleaned up code
v7 3/29/12:
    imporve modularization by removing the main() function
"""


def Loader(path, source=''):
    # takes in the path to the source and the source(filename) if specified
    # if no source is specified, this assumes that it is parsed directly
    # with the path
    img = nib.load(os.path.join(path, source))
    data = img.get_data().astype('float64')

    return ((img, data))


def HeadGrab(nifti):
    #takes in a nifti file and returns the head
    header = nifti.get_header()
    affine = nifti.get_affine()

    return ((header, affine))


def BatchReader(line, ages):
    # check if an age has been provided
    subConf = line.strip().split()
    ageStore = 1
    if len(subConf) == 1:
        print ('!You did not give an age for some or all of your subjects, '
               'SVR won\'t be available!')
        ageStore = 0

    sub = subConf[0]
    age = np.fromstring(subConf[1], dtype='float32', sep=' ')
    if ageStore == 1:
        ages = np.append(ages, age)
    else:
        ages = np.array([], dtype='float32')

    return (sub, ages)


def Masker(inData, maskData, maskNo):
    # takes in data of a functional file (possibly also anatomical),
    # the maskData and a maskNo
    # create output file of same dimensions as inData
    maskedOut = np.zeros(inData.shape, dtype='float32')
    # assign values inside the mask to the outfile
    maskedOut[maskData == maskNo] = inData[maskData == maskNo]
    cropMask = inData[maskData == maskNo]

    return ((maskedOut, cropMask))


def Averager(masked, averageArray=np.array([], dtype='float32')):
    # takes in a masked functional volume as an array of dimensions:
    # (voxels in map * timepoints)
    # averages over timepoints and stacks the returning averaged vector into
    # an increasing array if the function is called multiple times
    # if no array is handed over during calling, an empty array is used and
    # output will be identical to the averaged vector

    average = np.mean(masked, axis=0).astype('float32')
    if averageArray.size == 0:
        averageArray = average[np.newaxis, ...]
    else:
        averageArray = np.concatenate((averageArray,
                                       average[np.newaxis, ...]), axis=0)

    return ((average, averageArray))


def Correlater(averageArray, feature=np.array([], dtype='float32')):
    # takes in an array of any dimensions
    # treats the rows (axis=0) as observations and calculates a correlation
    # matrix
    # returns a vector of the lower diagonal of the matrix (created rowise)
    # and stacks vectors into an array if called multiple times

    corr = np.corrcoef(averageArray)
    matMask = np.ones_like(corr)
    # get the lower triangle of the matrix without the diagonal (-1)
    matMask = np.tril(matMask, -1)
    featVec = corr[matMask != 0]

    if feature.size == 0:
        feature = featVec[np.newaxis, ...]
    else:
        feature = np.concatenate((feature, featVec[np.newaxis, ...]), axis=0)

    return ((corr, featVec, feature))


def NifSaver(inFile, path, hdr, aff, prefix='outNiftiti', suffix='default'):
    # takes an array and writes it to a nifti. needs reasonable
    # affine and header information to do so
    outNifti = nib.Nifti1Image(inFile, aff, header=hdr)
    nib.nifti1.save(outNifti, (path + '/' + prefix + '_' + suffix + '.nii.gz'))


def TexSaver(inFile, path, prefix='avderage', suffix='default'):
    # writes anything to a textfile
    np.save((path + '/' + prefix + '_' + suffix + '.npy'), inFile)


def Processer(arguments):

    (sub,
     funcAbsPath,
     funcRelPath,
     funcName,
     maskData,
     outPath,
     texOut) = arguments

    # load the functional file
    (funcSet, funcData) = Loader(os.path.join(funcAbsPath, sub), funcName)
    feature = np.array([], dtype='float32')
    averageArray = np.array([], dtype='float32')

    for num in range(1, int(maskData.max() + 1)):
        # average the mask that was just run
        (outMask, smallMask) = Masker(funcData, maskData, num)
        (avgerage, averageArray) = Averager(smallMask,
                                            averageArray=averageArray)

        if texOut == 1:
            TexSaver(averageArray, (outPath + '/output'), prefix='average',
                     suffix=sub)

    (corr, featVec, feature) = Correlater(averageArray)

    print 'Done with Subject', sub, 'now '
    return featVec


def Main(batchFile, configFile, sysPath, saveOut=0):
    print '\nWelcome to the nifti Processer! '

    conf = open(os.path.join(sysPath, configFile)).readline().strip().split()
    (mPath,
     mSource,
     funcAbsPath,
     funcName,
     funcRelPath,
     outPath) = conf

    (mRaw, maskData) = Loader(mPath, source=mSource)
    batch = open(os.path.join(sysPath, batchFile))
    ages = np.array([], dtype='float32')
    argList = []
    texOut = 0

    for line in batch:
        (sub, ages) = BatchReader(line, ages)
        arguments = (sub,
                     funcAbsPath,
                     funcRelPath,
                     funcName,
                     maskData,
                     outPath,
                     texOut)
        argList.append(arguments)

    pool = Pool(processes=8)
    resultList = pool.map(Processer, argList)
    print type(resultList)
    print len(resultList)
    print 'Sub1 reslist:', resultList[1].shape

    feature = np.array([], dtype='float32')

    TexSaver(resultList,
             outPath,
             prefix='reslist',
             suffix='newall')

    for item in range(len(resultList)):
        if feature.size == 0:
            add = resultList[0]
            feature = add[np.newaxis, ...]
        else:
            add = resultList[item]
            feature = np.concatenate((feature, add[np.newaxis, ...]), axis=0)

    print 'Feature shape', feature.shape
    print 'Ages shape', ages.shape

    if saveOut != 0:
        print '\########## '
        print 'Saving data to files '
        TexSaver(feature,
                 outPath,
                 prefix='feature',
                 suffix=str(maskData.max()))
        TexSaver(ages,
                 outPath,
                 prefix='ages',
                 suffix=str(maskData.max()))
        print '\nDone saving! '
        print '########## '
    else:
        print '\########## '
        print 'Nothing will be saved because \'saveout\' has not been set. '
        print '########## '

    # Return the values if this was called from another module
    return (feature, ages)


# Boilerplate to call main():
if __name__ == '__main__':
    print 'Running in direct Call mode!'

    # Information from the configfile should be fetched here so Main() can
    # be cleaned up for modular use

    sysPath = os.path.abspath(os.curdir)
    batchFile = sys.argv[1]
    configFile = sys.argv[2]
    Main(batchFile, configFile, sysPath)
