# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import json
import dateparser
import traceback
import os

DATABASE_NAME = 'data.sqlite'
conn = sqlite3.connect(DATABASE_NAME)
c = conn.cursor()
c.execute(
    '''
    CREATE TABLE IF NOT EXISTS data (
        date text,
        time text,
        abbreviation_canton_and_fl text,
        ncumul_tested  integer,
        ncumul_conf integer,
        ncumul_hosp integer,
        ncumul_ICU integer,
        ncumul_vent integer,
        ncumul_released integer,
        ncumul_deceased integer,
        source text,
        UNIQUE(date, time, abbreviation_canton_and_fl)
    )
    '''
)
conn.commit()


def parse_page(soup, conn):
    data = {
        'date': None,
        'time': '',
        'area': 'BE',
        'tested': None,
        'confirmed': None,
        'hospitalized': None,
        'icu': None,
        'vent': None,
        'released': None,
        'deceased': None,
        'source': 'https://www.besondere-lage.sites.be.ch/besondere-lage_sites/de/index/corona/index.html',
    }

    # parse number of confirmed cases and deceased
    table = soup.find("h2", string=re.compile(".*Corona.*(e|E)rkrankungen.*Kanton.*Bern")).parent.find("table")
    mapping = {
         u'F\xe4lle': 'confirmed',
         u'Todesf\xe4lle': 'deceased',
    }
    header = table.find_all('th')
    cells = table.find_all('td')

    assert len(header) == 2, "The number of headers changed"
    assert len(cells) == 2, "The number of cells changed"

    for i, value in enumerate(header):
        data[mapping[value.string]] = int(cells[i].string)

    # parse the date
    date_str = re.search(": (.*)\)", soup.find(string=re.compile(".*Stand:.*")).string).group(1)
    update_datetime = dateparser.parse(
        date_str,
        languages=['de']
    )
    data['date'] = update_datetime.date().isoformat()
    c = conn.cursor()

    try:
        print(data)
        c.execute(
            '''
            INSERT INTO data (
                date,
                time,
                abbreviation_canton_and_fl,
                ncumul_tested,
                ncumul_conf,
                ncumul_hosp,
                ncumul_ICU,
                ncumul_vent,
                ncumul_released,
                ncumul_deceased,
                source
            )
            VALUES
            (?,?,?,?,?,?,?,?,?,?,?)
            ''',
            [
                data['date'],
                data['time'],
                data['area'],
                data['tested'],
                data['confirmed'],
                data['hospitalized'],
                data['icu'],
                data['vent'],
                data['released'],
                data['deceased'],
                data['source'],
            ]
        )
    except sqlite3.IntegrityError:
        print("Error: Data for this date + time has already been added")
    finally:
        conn.commit()
    

# canton bern - start url
start_url = 'https://www.be.ch/corona'

# get page with data on it
page = requests.get(start_url)
soup = BeautifulSoup(page.content, 'html.parser')

try:
    parse_page(soup, conn)
except Exception as e:
    print("Error: %s" % e)
    print(traceback.format_exc())
    raise
finally:
    conn.close()


# trigger GitHub Action API
if 'MORPH_GH_USER' in os.environ:
    gh_user = os.environ['MORPH_GH_USER']
    gh_token = os.environ['MORPH_GH_TOKEN']
    gh_repo = os.environ['MORPH_GH_REPO']

    url = 'https://api.github.com/repos/%s/dispatches' % gh_repo
    payload = {"event_type": "update"}
    headers = {'content-type': 'application/json'}
    r = requests.post(url, data=json.dumps(payload), headers=headers, auth=(gh_user, gh_token))
    print(r)

