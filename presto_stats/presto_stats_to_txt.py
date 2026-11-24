#Imports
import os
import subprocess
import webbrowser
import pandas as pd

#Pick the season to save: '2026' is the 2025-26 season and '2025' is the 2024-25 season
#SEASON = '2026'

#The Presto school list (its links are for the 2025-26 season)
CSV_FILE = '/Users/owner/Desktop/PrestoSports_2025.csv'

#Each season gets its own folder of saved text files
OUTPUT_FOLDER = '/Users/owner/Desktop/presto_text_' + SEASON

#The season text that appears in the school links
if SEASON == '2025':
    link_season = '2024-25'
else:
    link_season = '2025-26'

#Make the output folder if it is not there yet
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

#Read the school list (massey_name is the school, stats_url is its link)
schools = pd.read_csv(CSV_FILE)

saved = []
skipped = []
warnings = []

#Go through the schools one at a time
for index, row in schools.iterrows():
    team = str(row['massey_name']).strip()

    #Switch the link to the chosen season and go to the Coach's View page
    url = str(row['stats_url']).strip().split('?')[0].replace('2025-26', link_season) + '?tmpl=teaminfo-network-monospace-template&sort=ab&pos=h'
    file_path = os.path.join(OUTPUT_FOLDER, team + '.txt')

    #Skip schools that are already saved so the script can be stopped and restarted
    if os.path.exists(file_path):
        skipped.append(team)
        continue

    #Open the school's Coach's View page in your own browser
    print('')
    print(str(index + 1) + ' of ' + str(len(schools)) + ': ' + team)
    webbrowser.open(url)

    #You copy the page text by hand: click the page, Command+A, Command+C
    answer = input('Copy the page text (Command+A, Command+C), then press Enter. Type s to skip this school or q to quit: ').strip().lower()
    if answer == 'q':
        break
    if answer == 's':
        skipped.append(team)
        continue

    #Read what is on the clipboard
    text = subprocess.run(['pbpaste'], capture_output=True, text=True).stdout

    #Warn if it does not look like a stats page
    if len(text) < 500 or 'ERA' not in text:
        print('   WARNING: that does not look like the stats page, saving it anyway')
        warnings.append(team)

    #Save the text file named after the Massey name
    with open(file_path, 'w') as file:
        file.write(text)
    saved.append(team)
    print('   Saved ' + team + '.txt')

#Summary
print('')
print('Season:', SEASON)
print('Saved:', len(saved))
print('Skipped (already saved or skipped by you):', len(skipped))
print('Check these ones, they may be wrong:', warnings)
