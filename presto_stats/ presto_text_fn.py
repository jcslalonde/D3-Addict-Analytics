import os
import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

#This function turns a page where every cell is on its own line into one row per line (the real Ohio Northern page looks like this)
def join_cell_lines(page_text):

    #Keep only the lines that have text
    cells = [line.strip() for line in page_text.replace('\xa0', ' ').splitlines() if line.strip() != '']

    #If the page has no header made of single cells, it is already one row per line
    if not any(cells[i] in ['#', 'No.', 'No'] and cells[i + 1] == 'Player' for i in range(len(cells) - 1)):
        return page_text

    joined_lines = []
    i = 0
    while i < len(cells):

        #A header starts with # then Player, and ends at the first jersey number
        if cells[i] in ['#', 'No.', 'No'] and i + 1 < len(cells) and cells[i + 1] == 'Player':
            j = i + 2
            while j < len(cells) and not cells[j].isdigit():
                j += 1
            header_columns = cells[i + 2:j]
            joined_lines.append('# Player ' + ' '.join(header_columns))
            column_count = len(header_columns) + 2
            i = j

            #Read one row at a time while the row starts with a jersey number
            while i + column_count <= len(cells) and cells[i].isdigit() and not (cells[i + 1] in ['#', 'No.', 'No'] and cells[i + 2] == 'Player'):
                row = cells[i:i + column_count]
                joined_lines.append(row[0] + ' ' + row[1] + ' ' + ' '.join(row[2:]))
                i += column_count

            #The Total and Opponents rows come after the players, so mark the end of the table
            joined_lines.append('Opponents')
            continue

        i += 1

    return '\n'.join(joined_lines)

#This function reads the hitting and pitching tables from the text of a PrestoSports Coach's View page
def parse_coaches_text(page_text):

    #Put each row on its own line if the page has one cell per line
    page_text = join_cell_lines(page_text)

    #Rows that were skipped because the spacing was not what was expected
    skipped_rows = []

    #Rows for the two tables
    hitting_rows = []
    pitching_rows = []

    #Which table is being read (None until a header row is found, and again after the Opponents row)
    table_type = None
    header_columns = []

    #This function turns a stat from the page into a number (dashes mean 0)
    def to_number(token):
        if token in ['-', '–', '—', '']:
            return 0.0
        return float(token)

    #This function turns innings like 89.1 (89 and 1/3) into decimal innings
    def innings_to_decimal(token):
        if token in ['-', '–', '—', '']:
            return 0.0
        if '.' in token:
            whole, part = token.split('.')
            return int(whole or 0) + int(part or 0) / 3
        return float(token)

    #Go through the page one line at a time
    for line in page_text.replace('\xa0', ' ').splitlines():
        line_tokens = line.split()

        #Header rows start with # and Player
        if len(line_tokens) > 2 and line_tokens[0] in ['#', 'No.', 'No'] and line_tokens[1] == 'Player':
            header_columns = line_tokens[2:]
            if 'AVG' in header_columns:
                table_type = 'hitting'
            elif 'ERA' in header_columns:
                table_type = 'pitching'
            else:
                table_type = None
            continue

        #Skip lines outside the hitting and pitching tables and blank lines
        if table_type is None or len(line_tokens) == 0:
            continue

        #The Opponents row is the end of a table, and the Total row is skipped
        if line_tokens[0].startswith('Opponents'):
            table_type = None
            continue
        if line_tokens[0].startswith('Total'):
            continue

        #Player rows start with the jersey number (this also skips divider lines)
        if not line_tokens[0].isdigit():
            continue

        #A stat can be stuck to the dots after the name (Fusco.......342) so put a space before it
        fixed_line = re.sub(r'(?<=[A-Za-z.])\.(?=\d)', ' .', line)

        #Stats can also touch each other (.34924 means .349 and 24) so split after a 3 digit decimal
        fixed_line = re.sub(r'(\.\d{3})(?=\d)', r'\1 ', fixed_line)
        tokens = fixed_line.split()

        #The stats are the last tokens in the row, one for each header column
        column_count = len(header_columns)
        stats = tokens[-column_count:]
        name = re.sub(r'\.+$', '', ' '.join(tokens[1:-column_count])).strip()

        #Every stat must look like a number or a dash, otherwise the spacing is not what was expected
        name_has_numbers = any(re.match(r'^([-–—]|\d*\.?\d+)$', word) for word in tokens[1:-column_count])
        looks_right = len(tokens) >= column_count + 2 and name != '' and not name_has_numbers and all(re.match(r'^([-–—]|\d*\.?\d+|INF)$', stat) for stat in stats)
        if not looks_right:
            skipped_rows.append(line.strip())
            continue

        values = dict(zip(header_columns, stats))

        if table_type == 'hitting':
            at_bats = to_number(values.get('AB', '0'))

            #Only hitters with at bats can be used in the simulator
            if at_bats > 0:
                hitting_rows.append({
                    '#': tokens[0],
                    'Player': name,
                    'AVG': to_number(values.get('AVG', '0')),
                    'OBP': to_number(values.get('OB%', '0')),
                    '2B': to_number(values.get('2B', '0')),
                    '3B': to_number(values.get('3B', '0')),
                    'HR': to_number(values.get('HR', '0')),
                    'H': to_number(values.get('H', '0')),
                    'SO': to_number(values.get('SO', '0')),
                    'AB': at_bats,
                    'BB': to_number(values.get('BB', '0')),
                    'HBP': to_number(values.get('HBP', '0')),
                    'SF': to_number(values.get('SF', '0')),
                    'SB': to_number(values.get('SB', '0')),
                    'SB_ATT': to_number(values.get('SB', '0')) + to_number(values.get('CS', '0')),
                    'GDP': to_number(values.get('GDP', '0')),
                    'SH': to_number(values.get('SH', '0'))})

        elif table_type == 'pitching':
            innings = innings_to_decimal(values.get('IP', '0'))

            #Only pitchers with innings can be used in the simulator
            if innings > 0:
                pitching_rows.append({
                    '#': tokens[0],
                    'Player': name,
                    'IP': innings,
                    'H': to_number(values.get('H', '0')),
                    'R': to_number(values.get('R', '0')),
                    'ER': to_number(values.get('ER', '0')),
                    'BB': to_number(values.get('BB', '0')),
                    'SO': to_number(values.get('SO', '0')),
                    '2B': to_number(values.get('2B', '0')),
                    '3B': to_number(values.get('3B', '0')),
                    'HR': to_number(values.get('HR', '0')),
                    'AB': to_number(values.get('AB', '0')),
                    'B/AVG': to_number(values.get('B/AVG', '0')),
                    'WP': to_number(values.get('WP', '0')),
                    'HBP': to_number(values.get('HBP', '0')),
                    'BK': to_number(values.get('BK', '0')),
                    'SFA': to_number(values.get('SFA', '0')),
                    'SHA': to_number(values.get('SHA', '0'))})

    return pd.DataFrame(hitting_rows), pd.DataFrame(pitching_rows), skipped_rows

#This function turns the player JSON (used by some PrestoSports schools, like Endicott) into hitting and pitching tables
def parse_players_json(players_data):
    hitting_rows = []
    pitching_rows = []

    for player in players_data['individuals']:
        stats = player.get('stats', {})

        #The JSON can give stats as text (like '.210'), so turn each one into a number
        clean_stats = {}
        for key, value in stats.items():
            try:
                clean_stats[key] = float(value)
            except (TypeError, ValueError):
                clean_stats[key] = value
        stats = clean_stats
        player_name = player.get('fullName', '')
        uniform = player.get('uniform', '')

        #Find hitting stats
        at_bats = float(stats.get('ab', 0) or 0)
        if at_bats > 0:
            sb_attempts = int(stats.get('sb', 0) or 0) + int(stats.get('cs', 0) or 0)
            hitting_rows.append({
                '#': uniform,
                'Player': player_name,
                'AVG': stats.get('avg', 0),
                'OBP': stats.get('obp', 0),
                '2B': stats.get('hd', 0),
                '3B': stats.get('ht', 0),
                'HR': stats.get('hr', 0),
                'H': stats.get('h', 0),
                'SO': stats.get('k', 0),
                'AB': stats.get('ab', 0),
                'BB': stats.get('bb', 0),
                'HBP': stats.get('hbp', 0),
                'SF': stats.get('sf', 0),
                'SB': stats.get('sb', 0),
                'SB_ATT': sb_attempts,
                'GDP': stats.get('gdp', 0),
                'SH': stats.get('sh', 0)})

        #Find pitching stats
        innings = float(stats.get('ipraw', 0) or 0)
        if innings > 0:
            pitching_rows.append({
                '#': uniform,
                'Player': player_name,
                'IP': stats.get('ip', 0),
                'H': stats.get('ph', 0),
                'R': stats.get('pr', 0),
                'ER': stats.get('er', 0),
                'BB': stats.get('pbb', 0),
                'SO': stats.get('pk', 0),
                '2B': stats.get('phd', 0),
                '3B': stats.get('pht', 0),
                'HR': stats.get('phr', 0),
                'AB': stats.get('pab', 0),
                'B/AVG': stats.get('pavg', 0),
                'WP': stats.get('wp', 0),
                'HBP': stats.get('phbp', 0),
                'BK': stats.get('bk', 0),
                'SFA': stats.get('psf', 0),
                'SHA': stats.get('psh', 0)})

    return pd.DataFrame(hitting_rows), pd.DataFrame(pitching_rows)

#This function gets the hitting and pitching stats for a PrestoSports school from its Coach's View page (or from a saved copy of the page text)
def get_presto_stats(url, team_name='', saved_folder='/Users/owner/Desktop/presto_text/'):
    try:
        #Ensure the url is in the correct format and has no extra options
        url = str(url).strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        base_url = url.split('?')[0]

        #Use the saved page text first if there is one for this team
        saved_file = os.path.join(saved_folder, str(team_name).strip() + '.txt')
        if team_name != '' and os.path.exists(saved_file):
            with open(saved_file, 'r') as file:
                saved_hitting, saved_pitching, saved_skipped = parse_coaches_text(file.read())
            if len(saved_hitting) > 0 and len(saved_pitching) > 0:
                return saved_hitting, saved_pitching

        #Say what the script is
        headers = {'User-Agent': 'D3-Addict-Analytics (contact: jlalonde@bu.edu)'}

        hitting_table = None
        pitching_table = None
        skipped_rows = []
        notes = []

        #This function downloads a page and asks again if it gets a 202
        def download(page_url):
            response = requests.get(page_url, headers=headers, timeout=30)
            for attempt in range(3):
                if response.status_code != 202:
                    break
                time.sleep(5)
                response = requests.get(page_url, headers=headers, timeout=30)
            notes.append(str(response.status_code) + ' ' + page_url.split('?tmpl=')[-1][:45])
            return response

        #Build the list of Coach's View pages to try. The link on the school's own team page goes first
        coaches_urls = []
        try:
            team_response = download(base_url)
            if team_response.status_code == 200:
                team_soup = BeautifulSoup(team_response.text, 'html.parser')
                coach_tag = team_soup.find('a', string=re.compile(r'coach.{0,3}s view', re.I))
                if coach_tag is not None and coach_tag.get('href'):
                    coaches_urls.append(urljoin(base_url, coach_tag.get('href')))
        except Exception as e:
            notes.append(type(e).__name__)

        coaches_urls.append(base_url + '?tmpl=teaminfo-network-monospace-template&sort=ab&pos=h')
        coaches_urls.append(base_url + '?tmpl=teaminfo-network-monospace-json-template')

        #Try each page until both tables are found
        for coaches_url in coaches_urls:
            try:
                response = download(coaches_url)

                if response.status_code == 200:
                    #First try the plain text tables
                    page_text = BeautifulSoup(response.text, 'html.parser').get_text()
                    hit_df, pit_df, skipped = parse_coaches_text(page_text)
                    skipped_rows = skipped_rows + skipped

                    #If there are no text tables, look for the player JSON address on the page
                    if len(hit_df) == 0 and len(pit_df) == 0:
                        page_source = response.text.replace('\\/', '/')
                        json_urls = [urljoin(coaches_url, item) for item in re.findall(r'["\']([^"\'\s<>]+\.json[^"\'\s<>]*)["\']', page_source)]
                        json_urls = [item for item in json_urls if 'playerspagedata' in item.lower() or 'players' in item.lower()]
                        if len(json_urls) > 0:
                            json_response = download(json_urls[0])
                            if json_response.status_code == 200:
                                players_data = json_response.json()
                                if isinstance(players_data, dict) and 'individuals' in players_data:
                                    hit_df, pit_df = parse_players_json(players_data)

                    if hitting_table is None and len(hit_df) > 0:
                        hitting_table = hit_df
                    if pitching_table is None and len(pit_df) > 0:
                        pitching_table = pit_df

            except Exception as e:
                notes.append(type(e).__name__)

            if hitting_table is not None and pitching_table is not None:
                break
            time.sleep(1)

        #If the pages did not give both tables, look for a saved copy of the page text
        saved_path = os.path.join(saved_folder, str(team_name).strip() + '.txt')
        if (hitting_table is None or pitching_table is None) and team_name != '' and os.path.exists(saved_path):
            with open(saved_path, 'r') as file:
                hit_df, pit_df, skipped = parse_coaches_text(file.read())
            skipped_rows = skipped_rows + skipped
            if hitting_table is None and len(hit_df) > 0:
                hitting_table = hit_df
            if pitching_table is None and len(pit_df) > 0:
                pitching_table = pit_df

        #Tell the user about rows that were skipped
        if len(skipped_rows) > 0:
            print(f'Skipped {len(skipped_rows)} rows with unexpected spacing for {team_name}. The first one: {skipped_rows[0]}')

        #Stop with a clear message if a table is still missing
        if hitting_table is None or pitching_table is None:
            print(f'Could not get PrestoSports stats for {team_name or base_url} (page status codes: {notes}). Save the page text as {saved_path} to use it instead.')
            return None, None

        return hitting_table, pitching_table

    #Handle errors
    except Exception as e:
        print(f'Error retrieving PrestoSports stats: {type(e).__name__}: {e}')
        return None, None
