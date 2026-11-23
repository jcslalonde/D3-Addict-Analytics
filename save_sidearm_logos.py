#Imports
import os
import time
from io import BytesIO
from urllib.parse import urljoin
import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image

#Where the SIDEARM list is and where the logos get saved (change the first path if your SIDEARM.csv is somewhere else)
sidearm_file = '/Users/owner/Desktop/SIDEARM.csv'
logo_folder = '/Users/owner/Desktop/sidearm_logos/'
os.makedirs(logo_folder, exist_ok=True)

#Read the list of SIDEARM schools
schools = pd.read_csv(sidearm_file)
url_column = [col for col in schools.columns if 'url' in col.lower()][0]
headers = {'User-Agent': 'D3-Addict-Analytics (contact: jlalonde@bu.edu)'}

saved_count = 0
failed_teams = []

#Go through each school and save its logo as a PNG
for index, row in schools.iterrows():
    team = str(row['massey_name']).strip()
    save_path = logo_folder + team + '.png'

    #Skip schools that already have a logo
    if os.path.exists(save_path):
        continue

    logo_url = ''
    try:
        url = str(row[url_column]).strip()
        if 'https://' not in url:
            url = 'https://' + url

                #Find the logo in the page header, then the page's share image, then the page icon
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        logo_url = None
        logo_tag = soup.select_one('.main-header__logo img, img.d-inline-block.align-text-top')
        if logo_tag is not None:
            logo_url = logo_tag.get('src')

        if not logo_url:
            for tag_name, attributes, link_key in [('meta', {'property': 'og:image'}, 'content'), ('meta', {'name': 'twitter:image'}, 'content'), ('link', {'rel': 'apple-touch-icon'}, 'href')]:
                found_tag = soup.find(tag_name, attrs=attributes)
                if found_tag is not None and found_tag.get(link_key):
                    logo_url = found_tag.get(link_key)
                    break

        #Stop with a clear message (and the page title) if no logo was found
        if not logo_url:
            page_title = soup.title.string if soup.title is not None else 'no title'
            raise Exception('No logo found, page title: ' + str(page_title))

        logo_url = urljoin(url, logo_url)
        logo_response = requests.get(logo_url, headers=headers, timeout=15)
        logo_response.raise_for_status()

        #SVG logos have to be turned into a PNG, other logos are saved as PNG (an SVG is spotted by its link or its contents)
        is_svg = '.svg' in logo_url.lower() or b'<svg' in logo_response.content[:1000].lower()
        if is_svg:
            import cairosvg
            cairosvg.svg2png(bytestring=logo_response.content, write_to=save_path, output_height=300)
        else:
            Image.open(BytesIO(logo_response.content)).convert('RGBA').save(save_path)

        saved_count += 1
        print('Saved', team)

    except Exception as e:
        failed_teams.append(team)
        print('Failed', team, type(e).__name__, logo_url)

    time.sleep(1)

print('Saved', saved_count, 'logos')
print('Failed:', failed_teams)