""" Setup field laptop working directories

Optionally, create cryologger config files.

AT, April 2025
"""

import json
import os
import pandas as pd


## -----------------------------------------------------------
## CryoLogger config files

# Identify all cryologger sites
sites = pd.read_csv('/Users/atedston/Library/CloudStorage/OneDrive-UniversitédeLausanne/flowstate_share/fieldwork/campaign_2025/gps_routes/flowstate_field_locations_2025.csv')
sites = sites[sites['site_type'] == 'GNSS-A']

# Load default config file
config = json.load(open('cryologger_config.json', 'r'))

# Make a directory to save files to


# Work through the sites
for index, site in sites.iterrows():
    config['uid'] = site.short_name
    os.makedirs(site.short_name, exist_ok=True)
    path = os.path.join(site.short_name, 'config.json')
    with open(path, 'w') as fh:
        fh.write(json.dumps(config, indent=2))
