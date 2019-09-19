"""
This file intends to gather code specific to Sentinel 2
Original author: Ignacio Heredia
Date: February 2019

Adaptation
----------
Date: August 2019
Author: Daniel Garcia
Email: garciad@ifca.unican.es
Github: garciadd
"""

#APIs
import os, re, shutil
import numpy as np
from osgeo import gdal

#subfuctions
from sat_modules import gdal_utils

class sentinel():
    
    def __init__(self, tile_path, output_path):
        
        self.max_res = 60

        # Bands per resolution (bands should be load always in the same order)
        self.res_to_bands = {10: ['B4', 'B3', 'B2', 'B8'],
                             20: ['B5', 'B6', 'B7', 'B8A', 'B11', 'B12'],
                             60: ['B1', 'B9', 'B10']}
        
        self.band_desc = {10: {'B4': 'B4 Red	[665 nm]',
                               'B3': 'B3 Green	[560 nm]',
                               'B2': 'B2 Blue	[490 nm]',
                               'B8': 'B8 Near infrared	[842 nm]'},
                          20: {'B5': 'B5 Vegetation classification	[705 nm]',
                               'B6': 'B6 Vegetation classification	[740 nm]',
                               'B7': 'B7 Vegetation classification	[783 nm]',
                               'B8A': 'B8A Vegetation classification	[865 nm]',
                               'B11': 'B11 Snow / ice / cloud discrimination	[1610 nm]',
                               'B12': 'B12 Snow / ice / cloud discrimination	[2190 nm]'},
                          60: {'B1': 'B1 Aerosol detection	[443 nm]',
                               'B9': 'B9 Water vapour	[945 nm]',
                               'B10': 'B10 Cirrus	[1375 nm]'}}
        
        self. tile_path = tile_path
        self.output_path = output_path
        
    def read_config_file(self):
        
        # Process input tile name
        r = re.compile("^MTD_(.*?)xml$")
        matches = list(filter(r.match, os.listdir(self.tile_path)))
        if matches:
            xml_path = os.path.join(self.tile_path, matches[0])
        else:
            raise ValueError('No .xml file found.')

        # Open XML file and read band descriptions
        if not os.path.isfile(xml_path):
            raise ValueError('XML path not found.')
            
        raster = gdal.Open(xml_path)
        if raster is None:
            raise Exception('GDAL does not seem to support this file.')

        return raster
    
    def save_files(self, arr_bands):
        
        for res in self.sets.keys():
            tif_path = os.path.join(self.output_path, 'Sentinel_Bands_{}m.tif'.format(res))
            coor = self.coord[res]
            description = self.band_desc[res]
            bands = arr_bands[res]
            arr_b = []
            desc = []
            for i, b in enumerate(self.res_to_bands[res]):
                arr_b.append(bands[b])
                desc.append(description[b])
            gdal_utils.save_gdal(tif_path, np.array(arr_b), desc, coor['geotransform'], coor['geoprojection'], file_format='GTiff')
    
    
    def load_bands(self):
        
        self.raster = self.read_config_file()
        
        datasets = self.raster.GetSubDatasets()
        self.sets = {10: [], 20: [], 60: []}
        for dsname, dsdesc in datasets:
            for res in self.sets.keys():
                if '{}m resolution'.format(res) in dsdesc:
                    self.sets[res] += [(dsname, dsdesc)]
                    break
                
        # Getting the bands shortnames and descriptions
        data_bands = {10: {}, 20: {}, 60: {}}
        self.coord = {10: {}, 20: {}, 60: {}}

        for res in self.sets.keys():
            print ('Loading bands of Resolution {}'.format(res))
            ds_bands = gdal.Open(self.sets[res][0][0])
            data_bands[res] = ds_bands.ReadAsArray()
            self.coord[res]['geotransform'] = ds_bands.GetGeoTransform()
            self.coord[res]['geoprojection'] = ds_bands.GetProjection()
            
        arr_bands = {10: {}, 20: {}, 60: {}}
        for res in self.sets.keys():
            for i, band in enumerate(self.res_to_bands[res]):
                arr_bands[res][band] = data_bands[res][i]
    
        self.save_files(arr_bands)
        