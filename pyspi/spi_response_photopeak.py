import numpy as np
import h5py
import scipy.interpolate as interpolate
import scipy.integrate as integrate
from datetime import datetime
from astropy.time.core import Time

from IPython.display import HTML

from pyspi.io.package_data import get_path_of_data_file




def log_interp1d(xx, yy, kind='linear'):
    logx = np.log10(xx)
    # Avoid nan entries for yy=0 entries
    logy = np.log10(np.where(yy<=0, 1e-32, yy))
    lin_interp = interpolate.interp1d(logx, logy, kind=kind)
    log_interp = lambda zz: np.power(10.0, lin_interp(np.log10(zz)))
    return log_interp

class SPIResponse_Photopeak(object):
    def __init__(self, ebounds=None, time=None):
        """FIXME! briefly describe function
        :param time: Time object, with the time for which the valid response should be used
        :param ebounds: User defined ebins for binned effective area
        :returns: 
        :rtype: 
        """
        
        self._load_irfs(time)
        if ebounds is not None:
            self.set_binned_data_energy_bounds(ebounds)
        
    def _load_irfs(self, time=None):
        """FIXME! briefly describe function
        :param time: Time object, with the time for which the valid response should be used
        :returns: 
        :rtype: 
        """
        
        if time==None:
            irf_file = get_path_of_data_file('spi_irfs_database_4.hdf5')
            print('Using the default irfs. The ones that are valid between 10/05/27 12:45:00 and present (YY/MM/DD HH:MM:SS)')
            
        elif time<Time(datetime.strptime('031206 060000', '%y%m%d %H%M%S')):
            irf_file = get_path_of_data_file('spi_irfs_database_0.hdf5')
            print('Using the irfs that are valid between Start and 03/07/06 06:00:00 (YY/MM/DD HH:MM:SS)')
            
        elif time<Time(datetime.strptime('040717 082006', '%y%m%d %H%M%S')):
            irf_file = get_path_of_data_file('spi_irfs_database_1.hdf5')
            print('Using the irfs that are valid between 03/07/06 06:00:00 and 04/07/17 08:20:06 (YY/MM/DD HH:MM:SS)')

        elif time<Time(datetime.strptime('090219 095957', '%y%m%d %H%M%S')):
            irf_file = get_path_of_data_file('spi_irfs_database_2.hdf5')
            print('Using the irfs that are valid between 04/07/17 08:20:06 and 09/02/19 09:59:57 (YY/MM/DD HH:MM:SS)')

        elif time<Time(datetime.strptime('100527 124500', '%y%m%d %H%M%S')):
            irf_file = get_path_of_data_file('spi_irfs_database_3.hdf5')
            print('Using the irfs that are valid between 09/02/19 09:59:57 and 10/05/27 12:45:00 (YY/MM/DD HH:MM:SS)')

        else:
            irf_file = get_path_of_data_file('spi_irfs_database_4.hdf5')
            print('Using the irfs that are valid between 10/05/27 12:45:00 and present (YY/MM/DD HH:MM:SS)')

        irf_database = h5py.File(irf_file, 'r')

        self._energies_database = irf_database['energies'].value

        self._ebounds = self._energies_database
        self._ene_min = self._energies_database[:-1]
        self._ene_max = self._energies_database[1:]
        
        irf_data = irf_database['irfs']

        self._irfs = irf_data[()]

        #self._irfs = self._irfs[...,0]
        #self._irfs_nonphoto_1 = self._irfs[...,1]
        #self._irfs_nonphoto_2 = self._irfs[...,2]
        
        self._irf_xmin = irf_data.attrs['irf_xmin']
        self._irf_ymin = irf_data.attrs['irf_ymin']
        self._irf_xbin = irf_data.attrs['irf_xbin']
        self._irf_ybin = irf_data.attrs['irf_ybin']
        self._irf_nx = irf_data.attrs['nx']
        self._irf_ny = irf_data.attrs['ny']
        
        irf_database.close()

        self._n_dets = self._irfs.shape[1]
        
        
    def get_xy_pos(self, azimuth, zenith):
        """
        FIXME! briefly describe function

        :param azimuth: 
        x = np.cos(ra_sat)*np.cos(dec_sat):param zenith: 
        :returns: 
        :rtype: 

        """
        # np.pi/2 - zenith. TODO: Check if this is corect. Only a guess at the moment!
        # zenith = np.pi/2-zenith
        x = np.cos(azimuth)*np.cos(zenith)
        y = np.sin(azimuth)*np.cos(zenith)
        z = np.sin(zenith)

        zenith_pointing = np.arccos(x)
        azimuth_pointing = np.arctan2(z,y)
        
        x_pos = (zenith_pointing * np.cos(azimuth_pointing) - self._irf_xmin) / self._irf_xbin
        y_pos = (zenith_pointing * np.sin(azimuth_pointing) - self._irf_ymin) / self._irf_ybin

        return x_pos, y_pos

    def set_binned_data_energy_bounds(self, ebounds):
        """
        Change the energy bins for the binned effective_area
        :param ebounds: New ebinedges: ebounds[:-1] start of ebins, ebounds[1:] end of ebins
        :return:
        """

        if not np.array_equal(ebounds, self._ebounds):
            
            print('You have changed the energy boundaries for the binned effective_area calculation in the further calculations!')
            self._ene_min = ebounds[:-1]
            self._ene_max = ebounds[1:]
            self._ebounds = ebounds
        
    def effective_area_per_detector(self, azimuth, zenith):
        """FIXME! briefly describe function

        :param azimuth: 
        :param zenith: 
        :returns:  the effective area array (n_energie X n_detectors)


        """

        # get the x,y position on the grid
        x, y = self.get_xy_pos(azimuth, zenith)

        # compute the weights between the grids
        wgt, xx, yy = self._get_irf_weights(x, y)


        # If outside of the response pattern set response to zero
        try:
            # select these points on the grid and weight them together
            weighted_irf = self._irfs[..., xx, yy].dot(wgt)
            
        except IndexError:
            weighted_irf = np.zeros_like(self._irfs[...,20,20])
            
            
        return weighted_irf

    # WAY TO GO: Get irfs_ph, irfs_nonph1 and irfs_nonph2 for a given direction => build base drm from this direction
    # => Rebin this base drm to the wanted energy bins 

    def interpolated_effective_area(self, azimuth, zenith):
        """
        Return a list of interpolated effective area curves for
        each detector

        :param azimuth: 
        :param zenith: 
        :returns: 
        :rtype: 

        """

        weighted_irf = self.effective_area_per_detector(azimuth, zenith)

        
        
        interpolated_irfs = []
        
        for det_number in range(self._n_dets):

            #tmp = interpolate.interp1d(self._energies, weighted_irf[:, det_number])
            
            tmp = log_interp1d(self._energies_database, weighted_irf[:, det_number])
            
            interpolated_irfs.append(tmp)

        return interpolated_irfs
            


    def get_binned_effective_area(self, azimuth, zenith, ebounds=None, gamma=None):
        """FIXME! briefly describe function

        :param azimuth: 
        :param zenith: 
        :param ebounds: 
        :returns: 
        :rtype: 

        """

        interpolated_effective_area = self.interpolated_effective_area(azimuth, zenith)

        binned_effective_area_per_detector = []
        if ebounds is not None:
            self.set_binned_data_energy_bounds(ebounds)

                            
        n_energy_bins = len(self._ebounds) - 1
        
        for det in range(self._n_dets):

            effective_area = np.zeros(n_energy_bins)

            for i, (lo,hi) in enumerate(zip(self._ene_min, self._ene_max)):

                if gamma is not None:
                    integrand = lambda x: (x**gamma) * interpolated_effective_area[det](x)

                else:

                    integrand = lambda x: interpolated_effective_area[det](x)

                # TODO: Is this (hi-lo) factor correct? Must be normalized to bin size, correct?
                effective_area[i] =  integrate.quad(integrand, lo, hi)[0]/(hi-lo)

            
            binned_effective_area_per_detector.append(effective_area)

        self._binned_effective_area_per_detector = binned_effective_area_per_detector
        return np.array(binned_effective_area_per_detector)
    
    def get_binned_effective_area_det(self, det, ebounds=None, gamma=None):
        """FIXME! briefly describe function

        :param azimuth: 
        :param zenith: 
        :param ebounds: 
        :returns: 
        :rtype: 

        """

        interpolated_effective_area = self._current_interpolated_effective_area[det]

        if ebounds is not None:
            self.set_binned_data_energy_bounds(ebounds)

                            
        n_energy_bins = len(self._ebounds) - 1
        
        effective_area = np.zeros(n_energy_bins)

        for i, (lo,hi) in enumerate(zip(self._ene_min, self._ene_max)):

            if gamma is not None:
                integrand = lambda x: (x**gamma) * interpolated_effective_area(x)

            else:

                integrand = lambda x: interpolated_effective_area(x)

            # TODO: Is this (hi-lo) factor correct? Must be normalized to bin size, correct?
            effective_area[i] =  integrate.quad(integrand, lo, hi)[0]/(hi-lo)

            
        return effective_area
    
    def get_binned_effective_area_det_trapz(self, det, ebounds=None, gamma=None):
        """FIXME! briefly describe function

        :param azimuth: 
        :param zenith: 
        :param ebounds: 
        :returns: 
        :rtype: 

        """

        interpolated_effective_area = self._current_interpolated_effective_area[det]
        
        if ebounds is not None:
            self.set_binned_data_energy_bounds(ebounds)

        #effective_area = integrate.cumtrapz(interpolated_effective_area(self.ebounds), self.ebounds)                   
        n_energy_bins = len(self._ebounds) - 1
        
        #effective_area = np.zeros(n_energy_bins)

        #for i, (lo,hi) in enumerate(zip(self._ene_min, self._ene_max)):
            
        #    effective_area[i] = integrate.trapz([interpolated_effective_area(lo),interpolated_effective_area(hi)], [lo,hi])/(hi-lo)
        ebins = np.empty((len(self._ene_min), 2))
        eff_area = np.empty_like(ebins)

        ebins[:,0] = self._ene_min
        ebins[:,1] = self._ene_max

        inter = interpolated_effective_area(self._ebounds)
        
        eff_area[:,0] = inter[:-1]
        eff_area[:,1] = inter[1:]
        #x= interpolated_effective_area(self._ebounds)
        #y=self._ebounds
        #effective_area = integrate.cumtrapz(x,y)-integrate.cumtrapz(x[:-1], y[:-1], initial=0)
        effective_area = integrate.trapz(eff_area, ebins, axis=1)
        return effective_area/(self._ene_max-self._ene_min)

    def set_location(self, azimuth, zenith):
        """
        Update location and get new irf values for this location
        :param azimuth: Azimuth of position in spacecraft coordinates
        :param zenith: Zenith of position in spacecraft coordinates
        """
        azimuth = np.deg2rad(azimuth)
        zenith = np.deg2rad(zenith)

        self._current_interpolated_effective_area = self.interpolated_effective_area(azimuth, zenith)
    
    def get_eff_area_det(self, det, trapz=True):
        """
        Get the effective_area for the current position for all Ebins
        :param det: Detector
        :param trapz: Trapz integration? Much fast but can be inaccurate...
        """
        if trapz:
            return self.get_binned_effective_area_det_trapz(det)
        else:
            return self.get_binned_effective_area_det(det)
    
    @property
    def matrix(self):
        return self._matrix

    def _get_irf_weights(self, x_pos, y_pos):
        """FIXME! briefly describe function

        :param x_pos: 
        :param y_pos: 
        :returns: 
        :rtype: 

        """


        # get the four nearest neighbors
        ix_left = np.floor(x_pos) if (x_pos >= 0.0) else np.floor(x_pos) - 1
        iy_low = np.floor(y_pos) if (y_pos >= 0.0) else np.floor(y_pos) - 1

        ix_right = ix_left + 1
        iy_up = iy_low + 1

        wgt_right = float(x_pos - ix_left)
        wgt_up = float(y_pos - iy_low)



        
        # pre set the weights
        wgt = np.zeros(4)


        if ix_left < 0.:

            if ix_right < 0.:

                out = _prep_out_pixels(ix_left, ix_right, iy_low, iy_up)

                return wgt, out[0], out[1]

            else:

                ix_left = ix_right
                wgt_left = 0.5
                wgt_right = 0.5

        elif ix_right >= self._irf_nx:

            if ix_left >= self._irf_nx:

                out = _prep_out_pixels(ix_left, ix_right, iy_low, iy_up)

                return wgt, out[0], out[1]

            else:

                ix_right = ix_left
                wgt_left = 0.5
                wgt_right = 0.5

        else:

            wgt_left = 1. - wgt_right

        if iy_low < 0:
            if iy_up < 0:

                out = _prep_out_pixels(ix_left, ix_right, iy_low, iy_up)

                return wgt, out[0], out[1]
            else:
                iy_low = iy_up
                wgt_up = 0.5
                wgt_low = 0.5

        elif iy_up >= self._irf_ny:

            if iy_low >= self._irf_ny:

                out = _prep_out_pixels(ix_left, ix_right, iy_low, iy_up)

                return wgt, out[0], out[1]

            else:

                iy_up = iy_low
                wgt_up = 0.5
                wgt_low = 0.5

        else:

            wgt_low = 1. - wgt_up

        wgt[0] = wgt_left * wgt_low
        wgt[1] = wgt_right * wgt_low
        wgt[2] = wgt_left * wgt_up
        wgt[3] = wgt_right * wgt_up

        out = _prep_out_pixels(ix_left, ix_right, iy_low, iy_up)

        return wgt, out[0], out[1]


        

        


    
    def get_irf_weights_vector(self, x_pos, y_pos):

        raise NotImplementedError('Cannot do this yet')

        idx_x_neg = x_pos < 0.
        idx_y_neg = y_pos < 0.

        ix_left = x_pos
        iy_low = y_pos

        ix_left[idx_x_neg] -= 1
        iy_low[idx_y_neg] -= 1

        ix_right = ix_left + 1
        iy_up = iy_low + 1
        wgt_right = x_pos - ix_left
        wgt_up = y_pos - iy_low

        wgt_left = 1. - wgt_right
        wgt_low = 1. - wgt_up

        ############################################

        selection = (ix_left < 0.) & (ix_right >= 0.)

        wgt_left[selection] = 0.5
        wgt_right[selection] = 0.5

        ix_left[selection] = ix_right[selection]

        selection = (ix_right >= self._irf_nx) & (ix_left < self._irf_nx)

        wgt_left[selection] = 0.5
        wgt_right[selection] = 0.5

        ix_right[selection] = ix_left[selection]

        selection = (iy_low < 0) & (iy_up >= 0)

        iy_low[selection] = iy_up[selection]
        wgt_up[selection] = 0.5
        wgt_low[selection] = 0.5

        selection = (iy_up >= self._irf_ny) & (iy_low < self._irf_ny)

        iy_up[selection] = iy_low[selection]
        wgt_up[selection] = 0.5
        wgt_low[selection] = 0.5

        #         inx[0] = int(ix_left + iy_low * self._irf_nx)
        #         inx[1] = int(ix_right + iy_low * self._irf_nx)
        #         inx[2] = int(ix_left + iy_up * self._irf_nx)
        #         inx[3] = int(ix_right + iy_up * self._irf_nx)

        left_low = [int(ix_left), int(iy_low)]
        right_low = [int(ix_right), int(iy_low)]
        left_up = [int(ix_left), int(iy_up)]
        right_up = [int(ix_right), int(iy_up)]

        wgt[0] = wgt_left * wgt_low
        wgt[1] = wgt_right * wgt_low
        wgt[2] = wgt_left * wgt_up
        wgt[3] = wgt_right * wgt_up

        return inx, wgt,

    @property
    def irfs(self):

        return self._irfs

    @property
    def energies_database(self):
        return self._energies_database

    @property
    def ebounds(self):
        return self._ebounds

    @property
    def ene_min(self):
        return self._ene_min

    @property
    def ene_max(self):
        return self._ene_max

    def binned_effective_area_detector(self, det_number):
        return self._binned_effective_area_per_detector[det_number]
    
    @property
    def rod(self):
        """
        Ensure that you know what you are doing.

        :return: Roland
        """
        return HTML(filename=get_path_of_data_file('roland.html'))



def _prep_out_pixels(ix_left, ix_right, iy_low, iy_up):
    
    left_low = [int(ix_left), int(iy_low)]
    right_low = [int(ix_right), int(iy_low)]
    left_up = [int(ix_left), int(iy_up)]
    right_up = [int(ix_right), int(iy_up)]
    
    out = np.array([left_low, right_low, left_up, right_up]).T

    return out