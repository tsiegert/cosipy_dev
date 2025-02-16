# Imports:
import numpy as np
from astropy.table import Table
from astropy.io import fits
import h5py
import time
from cosipy.data_io import DataIO
import gzip
import astropy.coordinates as astro_co
import astropy.units as u
from astropy.coordinates import SkyCoord
from scoords import Attitude
from scoords import SpacecraftFrame
import logging
import sys
logger = logging.getLogger(__name__)

class UnBinnedData(DataIO):
 
    def read_tra(self):
        
        """
        Reads in MEGAlib .tra (or .tra.gz) file.
        Returns COSI dataset as a dictionary of the form:
        cosi_dataset = {'Full filename':self.data_file,
                        'Energies':erg,
                        'TimeTags':tt,
                        'Xpointings':np.array([lonX,latX]).T,
                        'Ypointings':np.array([lonY,latY]).T,
                        'Zpointings':np.array([lonZ,latZ]).T,
                        'Phi':phi,
                        'Chi local':chi_loc,
                        'Psi local':psi_loc,
                        'Distance':dist,
                        'Chi galactic':chi_gal,
                        'Psi galactic':psi_gal}
        
        Arrays contain unbinned data. 
        """
        
        # Make print statement:
        print("reading tra file...")
        
        # Initialise empty lists:
            
        # Total photon energy
        erg = []
        # Time tag in UNIX time
        tt = []
        # Event Type (CE or PE)
        et = []
        # Galactic latitude of X direction of spacecraft
        latX = []
        # Galactic lontitude of X direction of spacecraft
        lonX = []
        # Galactic latitude of Z direction of spacecraft
        latZ = []
        # Galactic longitude of Z direction of spacecraft
        lonZ = []
        # Compton scattering angle
        phi = []
        # Measured data space angle chi (azimuth direction; 0..360 deg)
        chi_loc = []
        # Measured data space angle psi (polar direction; 0..180 deg)
        psi_loc = []
        # Measured gal angle chi (lon direction)
        chi_gal = []
        # Measured gal angle psi (lat direction)
        psi_gal = [] 
        # Components of dg (position vector from 1st interaion to 2nd)
        dg_x = []
        dg_y = []
        dg_z = []

        # Define electron rest energy, which is used in calculation
        # of Compton scattering angle.
        c_E0 = 510.9989500015 # keV

        # Open tra file:
        if self.data_file.endswith(".gz"):
            f = gzip.open(self.data_file,"rt")
        elif self.data_file.endswith(".tra"):
            f = open(self.data_file,"r")
        else: 
            print()
            print("ERROR: Input data file must have '.tra' or '.gz' extenstion.")
            print()
            sys.exit()
        
        # Read tra file line by line:
        for line in f:
         
            this_line = line.strip().split()
            
            # Total photon energy and Compton angle: 
            if this_line[0] == "CE":

                # Compute the total photon energy:
                m_Eg = float(this_line[1]) # Energy of scattered gamma ray in keV
                m_Ee = float(this_line[3]) # Energy of recoil electron in keV
                this_erg = m_Eg + m_Ee
                erg.append(this_erg) 
             
                # Compute the Compton scatter angle due to the standard equation,
                # i.e. neglect the movement of the electron,
                # which would lead to a Doppler-broadening.
                this_value = 1.0 - c_E0 * (1.0/m_Eg - 1.0/(m_Ee + m_Eg))
                this_phi = np.arccos(this_value) # radians
                phi.append(this_phi)
            
            # Time tag in Unix time (seconds):
            if this_line[0] == "TI":
                tt.append(float(this_line[1]))

            # Event type: 
            if this_line[0] == "ET":
                et.append(this_line[1])

            # X axis of detector orientation in Galactic coordinates:
            if this_line[0] == "GX":
                this_lonX = np.deg2rad(float(this_line[1])) # radians
                this_latX = np.deg2rad(float(this_line[2])) # radians
                lonX.append(this_lonX)
                latX.append(this_latX)
            
            # Z axis of detector orientation in Galactic coordinates:
            if this_line[0] == "GZ":
                this_lonZ = np.deg2rad(float(this_line[1])) # radians
                this_latZ = np.deg2rad(float(this_line[2])) # radians
                lonZ.append(this_lonZ)
                latZ.append(this_latZ)
 
            # Interaction position information: 
            if (this_line[0] == "CH"):
                
                # First interaction:
                if this_line[1] == "0":
                    v1 = np.array((float(this_line[2]),\
                            float(this_line[3]),float(this_line[4])))
                
                # Second interaction:
                if this_line[1] == "1":
                    v2 = np.array((float(this_line[2]),
                        float(this_line[3]), float(this_line[4])))
                
                    # Compute position vector between first two interactions:
                    dg = v2 - v1
                    dg_x.append(dg[0])
                    dg_y.append(dg[1])
                    dg_z.append(dg[2])
        
        # Initialize arrays:
        erg = np.array(erg)
        phi = np.array(phi)
        tt = np.array(tt)
        et = np.array(et)
    
        latX = np.array(latX)
        lonX = np.array(lonX)
        # Change longitudes from 0..360 deg to -180..180 deg
        lonX[lonX > np.pi] -= 2*np.pi

        latZ = np.array(latZ)
        lonZ = np.array(lonZ)
        # Change longitudes from 0..360 deg to -180..180 deg
        lonZ[lonZ > np.pi] -= 2*np.pi 

        # Construct Y direction from X and Z direction
        lonlatY = self.construct_scy(np.rad2deg(lonX),np.rad2deg(latX),
                                np.rad2deg(lonZ),np.rad2deg(latZ))
        lonY = np.deg2rad(lonlatY[0])
        latY = np.deg2rad(lonlatY[1])
        self.latY_new = latY

        # Convert dg vector from 3D cartesian coordinates 
        # to spherical polar coordinates, and then extract distance 
        # b/n first two interactions (in cm), psi (rad), and chi (rad).
        # Note: the resulting angles are latitude/longitude (or elevation/azimuthal), 
        # i.e. the origin is along the equator rather than at the north pole.
        conv = astro_co.cartesian_to_spherical(np.array(dg_x), np.array(dg_y), np.array(dg_z))
        dist = conv[0].value 
        psi_loc = conv[1].value 
        chi_loc = conv[2].value
    
        # Rotate psi_loc to colatitude, 
        # measured from the negative z direction. 
        # Note: the detector is placed at z<0 in the local frame.
        # Note: the rotation is done to match the historical 
        # definition of COMPTEL.
        psi_loc += (np.pi/2.0)  

        # Rotate chi_loc to be defined relative to negative x-axis.
        # Note: this is done to match the historical definition of COMPTEL.
        index1 = (chi_loc < np.pi) 
        index2 = (chi_loc >= np.pi)
        chi_loc[index1] = chi_loc[index1] + np.pi
        chi_loc[index2] = chi_loc[index2] - np.pi
         
        # chi and psi in Galactic:
        
        # Define attitude:
        xcoords = SkyCoord(lonX*u.deg, latX*u.deg, frame = 'galactic')
        zcoords = SkyCoord(lonZ*u.deg, latZ*u.deg, frame = 'galactic')
        att = Attitude.from_axes(x=xcoords, z=zcoords, frame= 'galactic')
 
        chi_gal = np.array(chi_gal)
        psi_gal = np.array(psi_gal)
          
        # Make observation dictionary
        cosi_dataset = {'Energies':erg,
                        'TimeTags':tt,
                        'Xpointings':np.array([lonX,latX]).T,
                        'Ypointings':np.array([lonY,latY]).T,
                        'Zpointings':np.array([lonZ,latZ]).T,
                        'Phi':phi,
                        'Chi local':chi_loc,
                        'Psi local':psi_loc,
                        'Distance':dist,
                        'Chi galactic':chi_gal,
                        'Psi galactic':psi_gal} 
        self.cosi_dataset = cosi_dataset

        # Write unbinned data to file (either fits or hdf5):
        self.write_unbinned_output() 
        
        return 

    def construct_scy(self, scx_l, scx_b, scz_l, scz_b):
    
        """
        Construct y-coordinate of spacecraft/balloon given x and z directions
        Note that here, z is the optical axis
        param: scx_l   longitude of x direction
        param: scx_b   latitude of x direction
        param: scz_l   longitude of z direction
        param: scz_b   latitude of z direction
        """
        
        x = self.polar2cart(scx_l, scx_b)
        z = self.polar2cart(scz_l, scz_b)
    
        return self.cart2polar(np.cross(z,x,axis=0))

    def polar2cart(self, ra, dec):
    
        """
        Coordinate transformation of ra/dec (lon/lat) [phi/theta] polar/spherical coordinates
        into cartesian coordinates
        param: ra   angle in deg
        param: dec  angle in deg
        """
        
        x = np.cos(np.deg2rad(ra)) * np.cos(np.deg2rad(dec))
        y = np.sin(np.deg2rad(ra)) * np.cos(np.deg2rad(dec))
        z = np.sin(np.deg2rad(dec))
    
        return np.array([x,y,z])

    def cart2polar(self, vector):
    
        """
        Coordinate transformation of cartesian x/y/z values into spherical (deg)
        param: vector   vector of x/y/z values
        """
        
        ra = np.arctan2(vector[1],vector[0]) 
        dec = np.arcsin(vector[2])
    
        return np.rad2deg(ra), np.rad2deg(dec)

    def write_unbinned_output(self):

        # Data units:
        units=['keV','s','rad:[glon,glat]','rad:[glon,glat]',
                'rad:[glon,glat]','rad','rad','rad','cm','rad','rad']
            
        # For fits output: 
        if self.unbinned_output == 'fits':
            table = Table(list(self.cosi_dataset.values()),\
                    names=list(self.cosi_dataset.keys()), \
                    units=units, \
                    meta={'data file':ntpath.basename(self.data_file)})
            table.write("unbinned_data.fits", overwrite=True)
            os.system('gzip -f unbinned_data.fits')

        # For hdf5 output:
        if self.unbinned_output == 'hdf5':
            with h5py.File('unbinned_data.hdf5', 'w') as hf:
                for each in list(self.cosi_dataset.keys()):
                    dset = hf.create_dataset(each, data=self.cosi_dataset[each], compression='gzip')        
    
        return
