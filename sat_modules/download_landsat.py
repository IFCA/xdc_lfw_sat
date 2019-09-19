# -*- coding: utf-8 -*-

# Copyright 2018 Spanish National Research Council (CSIC)
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
Given two dates and region, download N Landsat Collections scenes from 
EarthExplorer.
The downloaded Landsat collection scenes are compatible with LANDSAT_8_C1

Parameters
----------
inidate: datetime.strptime("YYYY-MM-dd", "%Y-%m-%d")
enddate: datetime.strptime("YYYY-MM-dd", "%Y-%m-%d")
region: name of one reservoir saved in the "coord_reservoirs.json" file

Author: Daniel Garcia Diaz
Date: Sep 2018
"""

#imports subfunctions
from sat_modules import config
from sat_modules import utils
from sat_modules import landsat

#imports apis
import json
import requests
import re, os, shutil 
from tqdm import tqdm

class download_landsat:

    def __init__(self, inidate, enddate, region, coordinates, producttype = "LANDSAT_8_C1", path=None):
        """
        initialize the variables used in the landsat class

        Parameters
        ----------
        inidate : str "%Y-%m-%d"
        enddate : str "%Y-%m-%d"
        region : str. e.g: "CdP"
        """

        #Search parameter needed for download
        self.inidate = inidate.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.enddate = enddate.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.coord = coordinates
        self.producttype = producttype
        self.region = region

        #work path
        self.path = path

        #earth explorer api data
        api_version = '1.4.1'
        self.api_endpoint = 'https://earthexplorer.usgs.gov/inventory/json/v/{}/'.format(api_version)
        self.login_url = 'https://ers.cr.usgs.gov/login/'
        self.credentials = config.landsat_pass #landsat credentials


    def to_json(self, **kwargs):
        """Convert input arguments to a formatted JSON string
        as expected by the EE API.
        """
        return {'jsonRequest': json.dumps(kwargs)}


    def login(self):
        """Get an API key."""

        data = self.to_json(username=self.credentials["username"], password=self.credentials["password"], catalogID='EE')
        response = requests.post(self.api_endpoint + 'login?', data=data).json()

        if response['error']:
            print ('EE: {}'.format(response['error']))
        return response['data']


    def _get_tokens(self, body):
        """Get `csrf_token` and `__ncforminfo`."""

        csrf = re.findall(r'name="csrf_token" value="(.+?)"', body)
        ncform = re.findall(r'name="__ncforminfo" value="(.+?)"', body)

        return csrf, ncform


    def search(self):
        """
        build the query and get the Landsat Collections scenes from request def
        """

        #search parameters
        params = {'datasetName': self.producttype,
                  'includeUnknownCloudCover': False,
                  'maxResults': 1000,
                  'temporalFilter': {'startDate': self.inidate, 
                                     'endDate': self.enddate},
                  'spatialFilter': {'filterType': 'mbr',
                                    'lowerLeft': {'latitude': self.coord['S'], 
                                                  'longitude': self.coord['W']},
                                    'upperRight': {'latitude': self.coord['N'], 
                                                   'longitude': self.coord['E']}}
                  }

        key = self.login()
        params.update(apiKey=key)
        params = self.to_json(**params)

        url = self.api_endpoint + 'search'
        response = requests.get(url, params=params).json()

        if response['error']:
            print ('EE: {}'.format(response['error']))
        else:
            response = response['data']

        print('Found {} results from Landsat'.format(len(response['results'])))
        print('Retrieving {} results'.format(len(response['results'])))

        return response['results']


    def download(self):

        chunk_size=1024
        session = requests.session()
        rsp = session.get(self.login_url)
        csrf, ncform = self._get_tokens(rsp.text)

        payload = {'username': self.credentials['username'],
                   'password': self.credentials['password'],
                   'csrf_token': csrf,
                   '__ncforminfo': ncform
                   }

        rsp = session.post(self.login_url, data=payload, allow_redirects=False)

        #load the downloaded files
        with open(os.path.join(self.path, self.region, 'downloaded_files.json')) as data_file:
                downloaded_files = json.load(data_file)

        #results of the search
        results = self.search()

        for scene in results:

            ID = scene['entityId']
            #type and level of the data
            file = scene['displayId'].split('_')
            if not (file[1] == 'L1TP' and file[-1] == 'T1'):
                print ("    file {} not valid!!".format(ID))
                continue

            if ID in downloaded_files['Landsat 8']:
                print ("    file {} already downloaded".format(ID))
                continue
            
            #create path and folder for the scene
            tile_path = os.path.join(self.path, ID)
            output_path = os.path.join(self.download_path, self.region, ID)

            print ('    Downloading {} files'.format(ID))
            downloaded_files['Landsat 8'].append(ID)

            #file size
            band_url = 'https://earthexplorer.usgs.gov/download/12864/{}/STANDARD/EE'.format(ID)
            resp = session.get(band_url, stream=True, allow_redirects=True)
            total_size = int(resp.headers['content-Length'])

            #download
            with tqdm(total=total_size, unit_scale=True, unit='B') as pbar:
                with session.get(band_url, stream=True, allow_redirects=True) as r:
                    filename = r.headers['Content-Disposition'].split('=')[-1]
                    filename = os.path.join(self.tile_path, filename)
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                pbar.update(chunk_size)
            
            #preprocess data
            utils.unzip_tarfile(filename, tile_path)
            l = landsat.landsat(tile_path, output_path)
            l.load_bands()
            shutil.rmtree(self.tile_path)

        # Save the new list of files
        with open(os.path.join(self.path, self.region, 'downloaded_files.json'), 'w') as outfile:
            json.dump(downloaded_files, outfile)
