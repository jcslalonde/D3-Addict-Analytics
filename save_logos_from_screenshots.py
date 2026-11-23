import os
import webbrowser
import pandas as pd
from PIL import ImageGrab

#Where the logos are saved
logo_folder = '/Users/owner/Desktop/presto_logos/'
os.makedirs(logo_folder, exist_ok=True)

#Read the Presto school list
presto_schools = pd.read_csv('/Users/owner/Desktop/PrestoSports.csv').dropna(subset=['massey_name', 'stats_url'])

for i in range(len(presto_schools)):
    team_name = str(presto_schools.iloc[i]['massey_name']).strip()
    url = str(presto_schools.iloc[i]['stats_url']).strip()
    path = logo_folder + team_name + '.png'

    #Skip schools that already have a logo
    if os.path.exists(path):
        print(f'[{i + 1}/{len(presto_schools)}] {team_name}: already saved')
        continue

    print(f'\n[{i + 1}/{len(presto_schools)}] {team_name}')
    webbrowser.open(url)

    while True:
        answer = input('Press Cmd+Ctrl+Shift+4 and drag around the logo, then press Enter here (type s to skip): ').strip().lower()
        if answer == 's':
            break

        #Read the screenshot from the clipboard (Mac)
        screenshot = ImageGrab.grabclipboard()

        if screenshot is None or isinstance(screenshot, list):
            print('No screenshot on the clipboard. Try again.')
            continue

        screenshot.convert('RGBA').save(path)
        print(f'Saved {path}')
        break
