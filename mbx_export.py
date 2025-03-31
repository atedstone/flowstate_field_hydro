"""
Remote control of Mobotix Management Center to export video clips every hour within 
specified date range.

PRE-REQUISITES:
- Needs a JSON profile in the same directory as this script, named mxmc_profile_{profile}.json.
- Mx ManagementCenter must be open on this computer and it must have remote control enabled. 

USAGE:

    mbx_export.py 2026-06-01 2026-8-31 C:\\my_files\\export_location

FILENAMING:
- Folder schema: one folder per day, {date}_{clockstart}_{clockend}
- In each folder, filename schema: {camera_name}_{date}_{clockstart}_{clockend}.avi
- MXMC handles filenaming automatically, I am not aware of how to change the schema.
- MXMC only produces files for timestamps/ranges which are available. If a time
  range is not available, it continues gracefully.

ASSUMPTIONS:
- Only one camera connected to the ManagementCenter.
- This script uses the default port for MXMC; change the constant MXRC_URL if needed.

AVI CLIP QUALITY:
- Set the requested export quality in the JSON file using the 'quality' keyword.
- AVI file sizes vary dramatically as a function of the requested quality level.
- For 20 second clips, static indoor testing:
    - 'high', 170-190 Mb
    - 'medium', 45 Mb

TECHNICAL BACKGROUND (not relevant for field usage):
- We have to use vanilla urllib rather than Requests, because the latter enforces
  encoding of special characters such as + symbols. These symbols are used in 
  the format of datetime string required by the HTTP server of MXMC.
- Mobotix mandates HTTPS (i.e. secure) protocol, but as we don't have certificates
  then we need to allow unverified connections.
- For information on commands that MXMC supports, in your web browser navigate to 
  https://localhost:{port}/help.

Andrew Tedstone, March 2025.
andrew.tedstone@unil.ch

"""

import urllib.request
import ssl
import os
import sys
import json
import pandas as pd
import datetime as dt
import time
import argparse

# The URL and port for MXMC remote control 
MXRC_URL = 'https://localhost:57536'
# Datetime format used by MXMC
MBTX_DT_FMT = "%Y-%m-%d+%H:%M:%S"
# Format of JSON config file
JSON_FN_TEMPLATE = 'mxmc_profile_{}.json'

def _exec_http(cmd, payload, print_url=False):
    """ Provide the basic functionality to send a GET command to ManagementCenter. """
    url = os.path.join(MXRC_URL, cmd) 
    
    # Create the string of arguments
    payload_str = "&".join("%s=%s" % (k,v) for k,v in payload.items())

    # Combine the URL with the payload
    url = f'{url}?{payload_str}'

    # Display the URL if requested
    if print_url:
        print(url)  

    # MXMC requires HTTPS connection, but we don't have certificate for it.
    # Therefore use an unverified secure connection.
    ssl_context = ssl._create_unverified_context()
    
    # Make the request to MXMC
    with urllib.request.urlopen(url, context=ssl_context) as response:
        body = response.read()
        # Decode the bytes object to str
        character_set = response.headers.get_content_charset()
        decoded = body.decode(character_set)

    return decoded

def list_cameras():
    r = _exec_http('list', {'cameras':1})
    return r

def setup_export_profile(profile):
    """
    Loads a JSON file in working directory.
    profile: str
    """
    cmd = 'exports'
    args = {
        'create':1,
        'profile':profile
    }
    settings = json.load(open(JSON_FN_TEMPLATE.format(profile), 'r'))
    args.update(settings)
    r = _exec_http(cmd, args)
    return r

def delete_export_profile(profile):
    """ Delete our custom export profile from MXMC. """
    r = _exec_http('exports', {'delete':1, 'profile':profile})
    return r

def add_to_export_list(start, end):
    """ Add a time segment to the export list. """
    cmd = 'exports'
    args = {
        'add':1,
        'begin': start.strftime(MBTX_DT_FMT),
        'end': end.strftime(MBTX_DT_FMT),
        'audio': 'off',
    }
    r = _exec_http(cmd, args)
    return r

def run_export_list(profile, export_path, wait_monitor=True):
    """ Start the exports in the exports bar using the specified profile """

    cmd = 'exports'
    payload = {
        'export': 1,
        'profile': profile,
        'path':export_path
    }
    r = _exec_http(cmd, payload)

    # Wait on export, block further commands
    if wait_monitor:
        active = True
        print('\tWaiting for export to finish...')
        while active:
            active = active_export()                
            time.sleep(5)
    return

def active_export():
    """ Returns True if exports active, otherwise False """
    cmd = 'exports'
    payload = {'status':'1'}
    r = _exec_http(cmd, payload)
    n = bool(int(r))
    return n

def cli(
    date_begin, 
    date_end, 
    export_path,
    profile='default',
    freq='1h',    
    window='59Min'
    ):
    """ Command Line Interface for this script. """

    print(f'Looking for MxManagementCenter at {MXRC_URL}.')

    print(f'Cameras recognised by MXMC:')
    print(list_cameras())

    # Create the customised Export profile in MXMC according to our JSON file.
    setup_export_profile(profile)

    dates = pd.date_range(date_begin, date_end, freq='1D')
    for d in dates:
        print(d)

        # Treat each day as a single export batch
        times = pd.date_range(d, d+pd.Timedelta(hours=23), freq=freq)
        for t in times:
            # Every requested time frame gets added to the export bar, whether or not
            # it actually exists. MXMC only checks this once the Export is triggered.
            add_to_export_list(t, t+pd.Timedelta(window))
        
        # Run the exports for this day
        print('\tRunning export list')
        run_export_list(profile, export_path, wait_monitor=True)

        # Clear the exports list
        _exec_http('exports', {'clear':1})
        # Clear the MXMC progress info
        _exec_http('exports', {'clearProgress':1})

    print('Exports finished.')
    # Once finished, delete our custom export profile.
    delete_export_profile(profile)


if __name__ == '__main__':

    p = argparse.ArgumentParser('Control exports from Mobotix cameras through Mobotix Management Center.')

    p.add_argument('date_start', help='start date, yyyy-mm-dd', 
        type=lambda s: dt.datetime.strptime(s, '%Y-%m-%d'))
    p.add_argument('date_finish', help='end date, yyyy-mm-dd',
        type=lambda s: dt.datetime.strptime(s, '%Y-%m-%d'))
    p.add_argument('export_to', help='str, path to export the clips to', type=str)
    p.add_argument('-profile', default='greenland', type=str)

    args = p.parse_args()

    if not os.path.exists(args.export_to):
        raise IOError('Specified export directory does not exist.')

    jfn = JSON_FN_TEMPLATE.format(args.profile)
    if not os.path.exists(jfn):
        raise IOError(f'Specified JSON profile {jfn} does not exist.')

    cli(args.date_start, args.date_finish, args.export_to, profile=args.profile)

    
    


