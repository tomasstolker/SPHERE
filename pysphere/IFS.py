import os
import glob
import pandas as pd
import subprocess
import numpy as np

import imutils

from astropy.io import fits


# keywords to be saved
keywords = [
    # standard
    'INSTRUME', 
    'OBJECT', 'DATE-OBS', 'DATE', 'HIERARCH ESO DET FRAM UTC',

    # DPR
    'HIERARCH ESO DPR CATG', 'HIERARCH ESO DPR TYPE', 'HIERARCH ESO DPR TECH',
        
    # coordinates
    'HIERARCH ESO TEL GEOLAT', 'HIERARCH ESO TEL GEOLON',
    'HIERARCH ESO INS4 DROT1 RA', 'HIERARCH ESO INS4 DROT1 DEC',
    'HIERARCH ESO TEL ALT', 'HIERARCH ESO TEL AZ',    

    # SAXO
    'HIERARCH ESO AOS TTLOOP STATE', 'HIERARCH ESO AOS HOLOOP STATE',
    'HIERARCH ESO AOS IRLOOP STATE', 'HIERARCH ESO AOS PUPLOOP STATE',
    'HIERARCH ESO AOS VISWFS MODE',

    # CPI
    'HIERARCH ESO SEQ ARM',
    'HIERARCH ESO INS COMB ICOR', 'HIERARCH ESO INS COMB IFLT', 'HIERARCH ESO INS COMB POLA',
    'HIERARCH ESO INS4 FILT2 NAME',
    'HIERARCH ESO INS4 DROT2 BEGIN', 'HIERARCH ESO INS4 DROT2 END', 'HIERARCH ESO INS4 DROT2 MODE', 
    
    # IFS
    'HIERARCH ESO INS2 MODE', 'HIERARCH ESO INS2 COMB IFS',

    # IRDIS
    'HIERARCH ESO INS1 MODE',
    'HIERARCH ESO INS1 FILT NAME', 'HIERARCH ESO INS1 OPTI2 NAME',
    'HIERARCH ESO INS1 PAC X', 'HIERARCH ESO INS1 PAC Y',
    
    # detector
    'HIERARCH ESO DET SEQ1 DIT', 'HIERARCH ESO DET NDIT',

    # observing conditions
    'HIERARCH ESO TEL AIRM START', 'HIERARCH ESO TEL AIRM END',
    'HIERARCH ESO TEL AMBI FWHM START', 'HIERARCH ESO TEL AMBI FWHM END', 'HIERARCH ESO TEL IA FWHM',
    'HIERARCH ESO TEL AMBI TAU0', 'HIERARCH ESO TEL AMBI TEMP',
    'HIERARCH ESO TEL AMBI WINDSP', 'HIERARCH ESO TEL AMBI WINDDIR'
]

# short keywords
keywords_short = keywords.copy()
for idx in range(len(keywords_short)):
    key = keywords_short[idx]
    if key.find('HIERARCH ESO ') != -1:
        keywords_short[idx] = key[13:]
        

def sort_files(root_path):
    '''
    Sort all raw files and save result in a data frame

    Parameters
    ----------
    root_path : str
        Path to the dataset

    Returns
    -------
    files_info : dataframe
        Data frame with the information on raw files
    '''

    print('Sorting raw files')
    
    # list files
    files = glob.glob(os.path.join(root_path, 'raw', '*.fits'))
    files = [os.path.basename(f) for f in files]
    
    if len(files) == 0:
        raise ValueError('No raw FITS files in root_path directory')

    print(' * found {0} FITS files in {1}'.format(len(files), root_path))

    # files table
    files_info = pd.DataFrame(index=files, columns=keywords_short, dtype='float')

    raw_path = os.path.join(root_path, 'raw/')
    for f in files:
        hdu = fits.open(os.path.join(raw_path, f))
        hdr = hdu[0].header

        for k, sk in zip(keywords, keywords_short):
            files_info.loc[f, sk] = hdr.get(k)

        hdu.close()

    # processed column
    files_info.insert(len(files_info.columns), 'PROCESSED', False)
        
    # save files_info
    files_info.to_csv(os.path.join(root_path, 'files.csv'))
    
    return files_info


def files_association(root_path, files_info):
    '''
    Performs the calibration files association and a sanity check

    Parameters
    ----------
    root_path : str
        Path to the dataset
    
    files_info : dataframe
        The data frame with all the information on raw files
    '''

    print('Performing file associtation for calibrations')
    
    # IFS obs mode
    modes = files_info.loc[files_info['DPR CATG'] == 'SCIENCE', 'INS2 COMB IFS']
    if len(modes.unique()) != 1:
        raise ValueError('Sequence is mixing YJ and YJH observations.')

    mode = modes.unique()[0]    
    if mode == 'OBS_YJ':
        mode_short = 'YJ'
    elif mode == 'OBS_H':
        mode_short = 'YJH'
    else:
        raise ValueError('Unknown IFS mode {0}'.format(mode))

    # specific data frame for calibrations
    # keep static calibrations and sky backgrounds
    calibs = files_info[(files_info['DPR CATG'] == 'CALIB') |
                        ((files_info['DPR CATG'] == 'SCIENCE') & (files_info['DPR TYPE'] == 'SKY'))]
    
    ###############################################
    # static calibrations not dependent on science
    ###############################################
    
    # white flat
    cfiles = calibs[(calibs['DPR TYPE'] == 'FLAT,LAMP') & (calibs['INS2 COMB IFS'] == 'CAL_BB_2_{0}'.format(mode_short))]
    if len(cfiles) != 2:
        print(' * Error: there should be 2 flat files for white lamp!')
        
    # 1020 nm flat
    cfiles = calibs[(calibs['DPR TYPE'] == 'FLAT,LAMP') & (calibs['INS2 COMB IFS'] == 'CAL_NB1_1_{0}'.format(mode_short))]
    if len(cfiles) != 2:
        print(' * Error: there should be 2 flat files for 1020 nm filter!')

    # 1230 nm flat
    cfiles = calibs[(calibs['DPR TYPE'] == 'FLAT,LAMP') & (calibs['INS2 COMB IFS'] == 'CAL_NB2_1_{0}'.format(mode_short))]
    if len(cfiles) != 2:
        print(' * Error: there should be 2 flat files for 1230 nm filter!')

    # 1300 nm flat
    cfiles = calibs[(calibs['DPR TYPE'] == 'FLAT,LAMP') & (calibs['INS2 COMB IFS'] == 'CAL_NB3_1_{0}'.format(mode_short))]
    if len(cfiles) != 2:
        print(' * Error: there should be 2 flat files for 1300 nm filter!')

    # 1550 nm flat (YJH mode only)
    if mode_short == 'YJH':
        cfiles = calibs[(calibs['DPR TYPE'] == 'FLAT,LAMP') & (calibs['INS2 COMB IFS'] == 'CAL_NB4_2_{0}'.format(mode_short))]
        if len(cfiles) != 2:
            print(' * Error: there should be 2 flat files for 1550 nm filter!')

    # spectra position
    cfiles = calibs[(calibs['DPR TYPE'] == 'SPECPOS,LAMP') & (calibs['INS2 COMB IFS'] == mode)]
    if len(cfiles) != 1:
        print(' * Error: there should be 1 spectra position file!')

    # wavelength
    cfiles = calibs[(calibs['DPR TYPE'] == 'WAVE,LAMP') & (calibs['INS2 COMB IFS'] == mode)]
    if len(cfiles) != 1:
        print(' * Error: there should be 1 wavelength calibration file!')
    
    # IFU flat
    cfiles = calibs[(calibs['DPR TYPE'] == 'FLAT,LAMP') & (calibs['INS2 COMB IFS'] == mode)]
    if len(cfiles) != 1:
        print(' * Error: there should be 1 IFU flat file!')
    
    # calibs dark file
    cfiles = calibs[((calibs['DPR TYPE'] == 'DARK') | (calibs['DPR TYPE'] == 'DARK,BACKGROUND')) &
                    (calibs['DET SEQ1 DIT'].round(2) == 1.65)]
    if len(cfiles) != 1:
        print(' * Warning: there is no dark/background for the basic calibrations (DIT=1.6 sec). ' +
              'It is *highly recommended* to include one to obtain the best data reduction. ' +
              'A single dark/background file is sufficient, and it can easily be downloaded ' +
              'from the ESO archive')
    
    ##################################################
    # static calibrations that depend on science (DIT)
    ##################################################

    obj = files_info.loc[files_info['DPR CATG'] == 'SCIENCE', 'DPR TYPE'].apply(lambda s: s[0:6])
    DITs = files_info.loc[(files_info['DPR CATG'] == 'SCIENCE') & (obj == 'OBJECT'), 'DET SEQ1 DIT'].unique().round(2)

    # handle darks in a slightly different way because there might be several different DITs
    for DIT in DITs:
        # instrumental backgrounds
        cfiles = calibs[((calibs['DPR TYPE'] == 'DARK') | (calibs['DPR TYPE'] == 'DARK,BACKGROUND')) &
                        (calibs['DET SEQ1 DIT'].round(2) == DIT)]
        if len(cfiles) == 0:
            print(' * Warning: there is no dark/background for science files with DIT={0} sec. '.format(DIT) +
                  'it is *highly recommended* to include one to obtain the best data reduction. ' +
                  'A single dark/background file is sufficient, and it can easily be downloaded ' +
                  'from the ESO archive')
            
        # sky backgrounds
        cfiles = files_info[(files_info['DPR TYPE'] == 'SKY') & (files_info['DET SEQ1 DIT'].round(2) == DIT)]
        if len(cfiles) == 0:
            print(' * Warning: there is no sky background for science files with DIT={0} sec. '.format(DIT) +
                  'Using a sky background instead of an internal instrumental background can ' +
                  'usually provide a cleaner data reduction')

    # keep only some columns
    calibs = calibs[['DPR CATG', 'DPR TYPE', 'DPR TECH', 'INS2 COMB IFS', 'DET SEQ1 DIT', 'DET NDIT', 'PROCESSED']]
            
    # save
    calibs.to_csv(os.path.join(root_path, 'calibs.csv'))
    
    return calibs


def sph_ifs_cal_dark(root_path, calibs_info):
    '''
    Create the dark and background calibrations

    Parameters
    ----------
    root_path : str
        Path to the dataset

    calibs_info : dataframe
        The data frame with all the information on raw calibration files
    '''

    print('Creating darks and backgrounds')
    
    # check directories
    calib_path = os.path.join(root_path, 'calib/')
    if not os.path.exists(calib_path):
        os.makedirs(calib_path)

    sof_path = os.path.join(root_path, 'sof/')
    if not os.path.exists(sof_path):
        os.makedirs(sof_path)
        
    # get list of files
    raw = calibs_info[np.logical_not(calibs_info['PROCESSED'])]
    calibs = raw[(calibs_info['DPR TYPE'] == 'DARK') | (calibs_info['DPR TYPE'] == 'DARK,BACKGROUND') |
                 (calibs_info['DPR TYPE'] == 'SKY')]

    # loops on type and DIT value
    types = ['DARK', 'DARK,BACKGROUND', 'SKY']
    DITs  = calibs['DET SEQ1 DIT'].unique().round(2)

    for ctype in types:
        for DIT in DITs:            
            cfiles = calibs[(calibs['DPR TYPE'] == ctype) & (calibs['DET SEQ1 DIT'].round(2) == DIT)]
            files = cfiles.index

            # skip non-existing combinations
            if len(cfiles) == 0:
                continue
            
            print(' * {0} with DIT={1:.2f} sec ({2} files)'.format(ctype, DIT, len(cfiles)))

            # create sof
            sof = os.path.join(sof_path, 'dark_DIT={0:.2f}.sof'.format(DIT))
            file = open(sof, 'w')
            for f in files:
                file.write('{0}raw/{1}     {2}\n'.format(root_path, f, 'IFS_DARK_RAW'))
            file.close()

            # products
            dark_file = 'dark_DIT={0:.2f}.fits'.format(DIT)
            bpm_file  = 'dark_bpm_DIT={0:.2f}.fits'.format(DIT)

            # execute esorex    
            args = ['esorex',
                    '--msg-level=debug',
                    'sph_ifs_master_dark',
                    '--ifs.master_dark.coll_alg=2',
                    '--ifs.master_dark.sigma_clip=5.0',
                    '--ifs.master_dark.smoothing=5',
                    '--ifs.master_dark.min_acceptable=0.0',
                    '--ifs.master_dark.max_acceptable=2000.0',
                    '--ifs.master_dark.outfilename={0}{1}'.format(calib_path, dark_file),
                    '--ifs.master_dark.badpixfilename={0}{1}'.format(calib_path, bpm_file),
                    sof]
            proc = subprocess.run(args, stdout=subprocess.DEVNULL)

            if proc.returncode != 0:
                raise ValueError('esorex process was not successful')

            # store products
            calibs_info.loc[dark_file, 'DPR CATG'] = cfiles['DPR CATG'][0]
            calibs_info.loc[dark_file, 'DPR TYPE'] = cfiles['DPR TYPE'][0]
            calibs_info.loc[dark_file, 'INS2 COMB IFS'] = cfiles['INS2 COMB IFS'][0]
            calibs_info.loc[dark_file, 'DET SEQ1 DIT'] = cfiles['DET SEQ1 DIT'][0]
            calibs_info.loc[dark_file, 'PROCESSED'] = True
            calibs_info.loc[dark_file, 'PRO CATG'] = 'IFS_MASTER_DARK'

            calibs_info.loc[bpm_file, 'DPR CATG'] = cfiles['DPR CATG'][0]
            calibs_info.loc[bpm_file, 'DPR TYPE'] = cfiles['DPR TYPE'][0]
            calibs_info.loc[bpm_file, 'INS2 COMB IFS'] = cfiles['INS2 COMB IFS'][0]
            calibs_info.loc[bpm_file, 'PROCESSED'] = True
            calibs_info.loc[bpm_file, 'PRO CATG']  = 'IFS_STATIC_BADPIXELMAP'

    # save
    calibs_info.to_csv(os.path.join(root_path, 'calibs.csv'))


def compute_detector_flat(raw_flat_files, bpm_files=None):
    '''
    Compute a master detector flat and associated bad pixel map

    Parameters
    ----------
    raw_flat_files : list
        List of 2 raw flat files

    bpm_files : list
        List of bad pixel map files

    Returns
    -------
    flat : array
        Master detector flat

    bpm : array
        Bad pixel map from flat
    '''

    # read bad pixel maps
    if bpm_files is None:
        bpm_in = np.zeros((2048, 2048), dtype=np.uint8)
    else:
        bpm_in = np.zeros((2048, 2048), dtype=np.uint8)
        for f in bpm_files:
            data = fits.getdata(f)
            bpm_in = np.logical_or(bpm_in, data)
        
        bpm_in = bpm_in.astype(np.uint8)

    # read data
    ff0, hdr0 = fits.getdata(raw_flat_files[0], header=True)
    ff1, hdr1 = fits.getdata(raw_flat_files[1], header=True)

    # flatten if needed
    if ff0.ndim == 3:
        ff0 = np.median(ff0, axis=0)

    if ff1.ndim == 3:
        ff1 = np.median(ff1, axis=0)

    # create master flat
    DIT0 = hdr0['HIERARCH ESO DET SEQ1 DIT']
    DIT1 = hdr1['HIERARCH ESO DET SEQ1 DIT']
    
    if DIT0 > DIT1:
        flat = ff0 - ff1
    else:
        flat = ff1 - ff0

    # bad pixels correction
    # flat = imutils.sigma_clipping(flat, box=5, nsigma=5, iterate=True)
    # flat = imutils.sigma_clipping(flat, box=7, nsigma=5, iterate=True)

    flat = flat / np.median(flat)

    # final bad pixel map
    bpm = (flat <= 0.9) | (flat >= 1.1)
    bpm = bpm.astype(np.uint8)

    return flat, bpm

    
def sph_ifs_detector_flat(root_path, calibs_info):
    '''
    Create the detector flat calibrations

    Parameters
    ----------
    root_path : str
        Path to the dataset

    calibs_info : dataframe
        The data frame with all the information on raw calibration files
    '''

    print('Creating flats')

    # check directories
    raw_path = os.path.join(root_path, 'raw/')
    
    calib_path = os.path.join(root_path, 'calib/')
    if not os.path.exists(calib_path):
        os.makedirs(calib_path)

    sof_path = os.path.join(root_path, 'sof/')
    if not os.path.exists(sof_path):
        os.makedirs(sof_path)
    
    # get list of files
    raw = calibs_info[np.logical_not(calibs_info['PROCESSED'])]
    calibs = raw[(calibs_info['DPR TYPE'] == 'FLAT,LAMP') | (calibs_info['DPR TECH'] == 'IMAGE')]

    # IFS obs mode
    mode = files_info.loc[files_info['DPR CATG'] == 'SCIENCE', 'INS2 COMB IFS'].unique()[0]    
    if mode == 'OBS_YJ':
        mode_short = 'YJ'
    elif mode == 'OBS_H':
        mode_short = 'YJH'
    else:
        raise ValueError('Unknown IFS mode {0}'.format(mode))

    # bpm files
    cfiles = calibs_info[calibs_info['PRO CATG'] == 'IFS_STATIC_BADPIXELMAP'].index
    bpm_files = [os.path.join(calib_path, f) for f in cfiles]
    
    # loop on wavelengths
    waves = [         0,        1020,        1230,        1300,        1550]
    combs = ['CAL_BB_2', 'CAL_NB1_1', 'CAL_NB2_1', 'CAL_NB3_1', 'CAL_NB4_2']
    lamps = [         5,           1,           2,           3,           4]
    
    for wave, comb, lamp in zip(waves, combs, lamps):
        print(' * flat for wavelength {0} nm (filter {1}, lamp {2})'.format(wave, comb, lamp))
        
        cfiles = calibs[calibs['INS2 COMB IFS'] == '{0}_{1}'.format(comb, mode_short)]
        files = [os.path.join(raw_path, f) for f in cfiles.index]

        if len(files) == 0:
            continue
        elif len(files) != 2:
            raise ValueError('There should be exactly 2 raw flat files ({0} found)'.format(len(files)))

        # create the flat and bpm
        flat, bpm = compute_detector_flat(files, bpm_files=bpm_files)
    
        # products
        flat_file = 'master_detector_flat_l{0}.fits'.format(lamp)
        bpm_file  = 'dff_badpixels_l{0}.fits'.format(lamp)        

        hdu = fits.open(os.path.join(raw_path, files[0]))
        fits.writeto(os.path.join(calib_path, flat_file), flat, header=hdu[0].header, output_verify='silentfix', overwrite=True)
        fits.writeto(os.path.join(calib_path, bpm_file), bpm, header=hdu[0].header, output_verify='silentfix', overwrite=True)
        hdu.close()
        
        # store products
        calibs_info.loc[flat_file, 'DPR CATG'] = cfiles['DPR CATG'][0]
        calibs_info.loc[flat_file, 'DPR TYPE'] = cfiles['DPR TYPE'][0]
        calibs_info.loc[flat_file, 'INS2 COMB IFS'] = cfiles['INS2 COMB IFS'][0]
        calibs_info.loc[flat_file, 'DET SEQ1 DIT'] = cfiles['DET SEQ1 DIT'][0]
        calibs_info.loc[flat_file, 'PROCESSED'] = True
        calibs_info.loc[flat_file, 'PRO CATG'] = 'IFS_MASTER_DFF'

        calibs_info.loc[bpm_file, 'DPR CATG'] = cfiles['DPR CATG'][0]
        calibs_info.loc[bpm_file, 'DPR TYPE'] = cfiles['DPR TYPE'][0]
        calibs_info.loc[bpm_file, 'INS2 COMB IFS'] = cfiles['INS2 COMB IFS'][0]
        calibs_info.loc[bpm_file, 'PROCESSED'] = True
        calibs_info.loc[bpm_file, 'PRO CATG']  = 'IFS_STATIC_BADPIXELMAP'

        return
        
    # save
    calibs_info.to_csv(os.path.join(root_path, 'calibs.csv'))



    

root_path = '/Users/avigan/data/pySPHERE-test/IFS/'

# files_info = sort_files(root_path)

files_info = pd.read_csv(root_path+'files.csv', index_col=0)
# calibs_info = files_association(root_path, files_info)

calibs_info = pd.read_csv(root_path+'calibs.csv', index_col=0)
# sph_ifs_dark(root_path, calibs_info)
sph_ifs_detector_flat(root_path, calibs_info)