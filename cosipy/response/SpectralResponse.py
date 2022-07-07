from copy import deepcopy

from .quantity_histogram import QuantityHistogram

import astropy.units as u

class SpectralResponse(QuantityHistogram):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self._aeff = None
    
    def get_dispersion_matrix(self):

        # Get effective area normalization
        norm = self.get_effective_area().full_contents

        # Hack the under/overflow bins to supress 0/0 wearning
        norm[0] = 1 if norm[0] == 0 else norm[0]
        norm[-1] = 1 if norm[-1] == 0 else norm[-1]

        # "Broadcast" such that it has the compatible dimensions with the 2D matrix
        norm = self.expand_dims(norm, 'Ei')
        
        # Normalize column-by-column
        return (self / norm)

    def get_effective_area(self, energy = None):

        if self._aeff is None:
            self._aeff = self.project('Ei').to_dense()

        if energy is None:
            return deepcopy(self._aeff)
        else:
            energy = energy.to_value(self._aeff.axis.unit)
            return self._aeff.interp(energy)*self.unit

    @property
    def photon_energy_axis(self):
        return self.axes['Ei']
        
    @property
    def measured_energy_axis(self):
        return self.axes['Em']
        

        
