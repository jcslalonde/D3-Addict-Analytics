#Imports
import os
import random
import time
from io import BytesIO, StringIO
from math import exp
from urllib.parse import urljoin
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

import sys
#Find presto_text_fn.py wherever it is in the repo
for folder, subfolders, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
    if 'presto_text_fn.py' in files:
        sys.path.append(folder)
        break
        
from presto_text_fn import parse_coaches_text

#Everything is read from the repo folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRESTO_TEXT_FOLDER = os.path.join(BASE_DIR, 'presto_stats', 'presto_text')
PRESTO_LOGO_FOLDER = os.path.join(BASE_DIR, 'presto_logos', 'presto_logos')
SIDEARM_LOGO_FOLDER = os.path.join(BASE_DIR, 'sidearm_logos')
MASSEY_FILE = os.path.join(BASE_DIR, 'massey_ratings', 'massey_ratings_eoy26.csv')

#Edit this when the saved Presto text files are refreshed
PRESTO_DATA_DATE = 'Nov 23, 2026'

#Read in the team lists
presto_schools = pd.read_csv(os.path.join(BASE_DIR, 'site_stats', 'PrestoSports.csv'))
sidearm_schools = pd.read_csv(os.path.join(BASE_DIR, 'site_stats', 'SIDEARM.csv'))

presto_names = presto_schools['massey_name'].dropna().astype(str).str.strip().tolist()
sidearm_names = sidearm_schools['massey_name'].dropna().astype(str).str.strip().tolist()
all_team_names = sorted(set(presto_names + sidearm_names))

#Chance that a runner on second scores on a single (otherwise he goes to third)
second_scores_single = 0.65

#This function finds a team's stats page link from the PrestoSports or SIDEARM file
def get_team_url(team_name):
    team_name = str(team_name).strip()
    for schools in [presto_schools, sidearm_schools]:
        match = schools[schools['massey_name'].astype(str).str.strip() == team_name]
        if not match.empty:
            url_column = [col for col in schools.columns if 'url' in col.lower()][0]
            return str(match.iloc[0][url_column]).strip()
    return None

#This function reads a PrestoSports team's saved page text from the repo (it never goes online)
def get_saved_presto_stats(team_name):
    path = os.path.join(PRESTO_TEXT_FOLDER, team_name + '.txt')
    if not os.path.exists(path):
        return None, None

    with open(path, 'r') as file:
        hitting, pitching, skipped = parse_coaches_text(file.read())

    if len(hitting) == 0 or len(pitching) == 0:
        return None, None
    return hitting, pitching

#This function scrapes the hitting and pitching stats from a team's website (SIDEARM only)
def get_sidearm_stats(url):

    #Ensure the url is in the correct format
    url = url.strip()
    if 'https://' not in url:
        url = 'https://' + url

    try:
        headers = {'User-Agent': 'D3-Addict-Analytics (contact: jlalonde@bu.edu)'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        #Turn every table on the page into a pandas table
        tables = pd.read_html(StringIO(response.text))

        hitting = None
        pitching = None

        #Find the hitting and pitching tables
        for table in tables:
            if 'OPS' in table.columns and hitting is None:
                hitting = table
            if 'ERA' in table.columns and pitching is None:
                pitching = table

        #Remove the Totals and Opponent rows
        hitting = hitting.iloc[:-2].reset_index(drop=True)
        pitching = pitching.iloc[:-2].reset_index(drop=True)

        #Fix the Player name column (currently appears as: Last, First Number Last, First)
        hitting['Player'] = (hitting['Player'].str.split(',').str[2] + ' ' + hitting['Player'].str.split(',').str[0]).str.strip()
        pitching['Player'] = (pitching['Player'].str.split(',').str[2] + ' ' + pitching['Player'].str.split(',').str[0]).str.strip()

        #Drop the Bio Links
        hitting = hitting.drop(columns='Bio Link')
        pitching = pitching.drop(columns='Bio Link')

        #Remove rows with missing jersey numbers
        hitting = hitting.dropna(subset=['#'])
        pitching = pitching.dropna(subset=['#'])

        #Change jersey number to str
        hitting['#'] = hitting['#'].astype(int).astype(str)
        pitching['#'] = pitching['#'].astype(int).astype(str)

        #Put SB and ATT into their own columns and drop the current one for the hitting table
        hitting['SB'] = hitting['SB-ATT'].str.split('-').str[0]
        hitting['SB_ATT'] = hitting['SB-ATT'].str.split('-').str[1]
        hitting = hitting.drop(columns='SB-ATT')

        #Change SB and SB_ATT to numbers
        hitting['SB'] = hitting['SB'].astype(int)
        hitting['SB_ATT'] = hitting['SB_ATT'].astype(int)

        return hitting, pitching

    except Exception:
        return None, None

#This function loads a team's stats (Sidearm is remembered for 6 hours so many users do not keep hitting the school's site)
@st.cache_data(ttl=21600, show_spinner=False)
def load_team_stats(team_name):
    if team_name in presto_names:
        return get_saved_presto_stats(team_name)

    url = get_team_url(team_name)
    if url is None:
        return None, None
    return get_sidearm_stats(url)

#This function loads a team's logo (saved Presto logo first, then the school's own page)
@st.cache_data(ttl=86400, show_spinner=False)
def load_logo(team_name):
    try:
        #Use the saved logo first if there is one
        saved_logo = os.path.join(PRESTO_LOGO_FOLDER, team_name + '.png')
        if os.path.exists(saved_logo):
            return plt.imread(saved_logo)

        #Presto schools without a saved logo just get none (their sites block scripts)
        if team_name in presto_names:
            return None

        url = get_team_url(team_name)
        headers = {'User-Agent': 'D3-Addict-Analytics (contact: jlalonde@bu.edu)'}
        response = requests.get(url, headers=headers, timeout=10)

        #Look for the logo image in the page header, then the page's share image
        soup = BeautifulSoup(response.text, 'html.parser')
        logo_tag = soup.select_one('.main-header__logo img, img.d-inline-block.align-text-top')
        if logo_tag is not None:
            logo_url = logo_tag.get('src')
        else:
            logo_tag = soup.find('meta', property='og:image')
            logo_url = logo_tag.get('content') if logo_tag is not None else None

        if not logo_url:
            return None

        logo_url = urljoin(url, logo_url)
        logo_response = requests.get(logo_url, headers=headers, timeout=10)
        logo_response.raise_for_status()

        #SVG logos have to be turned into a PNG first
        if '.svg' in logo_url.lower():
            import cairosvg
            png_bytes = cairosvg.svg2png(bytestring=logo_response.content, output_height=300)
            return plt.imread(BytesIO(png_bytes), format='png')

        return plt.imread(BytesIO(logo_response.content))

    except Exception:
        return None

#This function finds the offensive and defensive rating index of the teams from the saved Massey file
def massey_weights(off_team, def_team):
    try:
        massey_data = pd.read_csv(MASSEY_FILE)

        #Finds the matches for the input offensive and defensive teams
        match_off = massey_data[massey_data.iloc[:, 0].astype(str).str.lower().str.strip() == off_team.lower()]
        match_def = massey_data[massey_data.iloc[:, 0].astype(str).str.lower().str.strip() == def_team.lower()]

        if match_off.empty or match_def.empty:
            return None

        #Find which column number is for the offensive and defensive rankings
        off_position = massey_data.columns.get_loc('Off')
        def_position = massey_data.columns.get_loc('Def')

        #Gets the offensive and defensive ratings
        off_rating = float(match_off.iloc[:, off_position + 1].item())
        def_rating = float(match_def.iloc[:, def_position + 1].item())

        #Find standardized defensive and offensive rating index
        off_mean = massey_data['Unnamed: 10'].astype(float).mean()
        def_mean = massey_data['Unnamed: 12'].astype(float).mean()
        off_sd = massey_data['Unnamed: 10'].astype(float).std()
        def_sd = massey_data['Unnamed: 12'].astype(float).std()

        return float((off_rating - off_mean) / off_sd), float((def_rating - def_mean) / def_sd)

    except Exception:
        return None

#Single plate appearance
def plate_appearance(prob_row):
    bb_plus = 'Yes' if random.random() <= prob_row['P(BB+)'] else 'No'
    hit = 'No'
    xbh = 'No'
    xbh_type = None
    k = 'No'
    ipo = 'No'
    gdp = 'No'

    if bb_plus == 'No':
        hit = 'Yes' if random.random() <= prob_row['P(H)'] else 'No'

        if hit == 'Yes':
            xbh = 'Yes' if random.random() <= prob_row['P(XBH | H)'] else 'No'

            if xbh == 'Yes':
                xbh_type = random.choices(['2B', '3B', 'HR'], weights=[prob_row['P(2B | XBH)'], prob_row['P(3B | XBH)'], prob_row['P(HR | XBH)']])[0]

        else:
            k = 'Yes' if random.random() <= min(1, prob_row['P(K)'] / (1 - prob_row['P(H)'])) else 'No'
            if k == 'No':
                ipo = 'Yes'
                gdp = 'Yes' if random.random() <= prob_row['P(GDP)'] else 'No'

    if bb_plus == 'Yes':
        return 'bb_plus'
    elif hit == 'Yes' and xbh == 'No':
        return '1B'
    elif xbh == 'Yes':
        return xbh_type
    elif k == 'Yes':
        return 'k'
    elif ipo == 'Yes' and gdp == 'Yes':
        return 'gdp'
    return 'ipo'

#Moves every runner and the batter n bases and each base holds the lineup spot of the runner on it
def advance(first, second, third, batter_spot, n):
    new_first = 0
    new_second = 0
    new_third = 0
    scorers = []

    #Runner on third scores on any hit
    if third != 0:
        scorers.append(third)

    #Runner on second scores on a double or better, and on a single some of the time (otherwise goes to third)
    if second != 0:
        if n >= 2:
            scorers.append(second)
        elif random.random() < second_scores_single:
            scorers.append(second)
        else:
            new_third = second

    #Runner on first goes to second on a single, third on a double, and scores on a triple or home run
    if first != 0:
        if n == 1:
            new_second = first
        elif n == 2:
            new_third = first
        else:
            scorers.append(first)

    #The batter ends up on the base for the hit, or scores on a home run
    if n == 1:
        new_first = batter_spot
    elif n == 2:
        new_second = batter_spot
    elif n == 3:
        new_third = batter_spot
    else:
        scorers.append(batter_spot)

    return new_first, new_second, new_third, scorers

#Walk or hit by pitch (runners only move if forced)
def walk(first, second, third, batter_spot):
    scorers = []
    if first != 0:
        if second != 0:
            if third != 0:
                scorers.append(third)
            third = second
        second = first
    first = batter_spot
    return first, second, third, scorers

#This function runs the 40 game sim and returns everything the page shows
def simulate(hitting_table, pitcher_stats, off_weight, def_weight):

    #Save the hitter names in lineup order for the report
    hitter_names = hitting_table['Player'].tolist()
    pitcher_name = pitcher_stats['Player'].iloc[0]

    hitting_table = hitting_table.reset_index(drop=True)
    pitching_table = pitcher_stats.reset_index(drop=True)

    #Creating weight multipliers
    w_off = exp(off_weight * 0.1)
    w_def = exp(def_weight * 0.1)

    #Offensive adjustments and calculations
    hitting_table['W_AVG'] = hitting_table['AVG'] * w_off
    hitting_table['XBH'] = hitting_table['2B'] + hitting_table['3B'] + hitting_table['HR']
    hitting_table['W_XBH/H'] = (hitting_table['XBH'] / hitting_table['H']) * w_off

    hitting_table['%XBH_AS_2B'] = hitting_table['2B'] / hitting_table['XBH']
    hitting_table['%XBH_AS_3B'] = hitting_table['3B'] / hitting_table['XBH']
    hitting_table['%XBH_AS_HR'] = hitting_table['HR'] / hitting_table['XBH']

    hitting_table['W_K_RT'] = (hitting_table['SO'] / hitting_table['AB']) / w_off
    hitting_table['W_BB+_RT'] = ((hitting_table['BB'] + hitting_table['HBP']) / (hitting_table['AB'] + hitting_table['BB'] + hitting_table['HBP'] + hitting_table['SF'])) * w_off

    hitting_table['W_SB_ATT_RT'] = (hitting_table['SB_ATT'] / (hitting_table['H'] + hitting_table['BB'] + hitting_table['HBP'])) * w_off
    hitting_table['W_SB%'] = (hitting_table['SB'] / hitting_table['SB_ATT']) * w_off

    hitting_table['W_GDP'] = (hitting_table['GDP'] / (hitting_table['AB'] - hitting_table['SO'] - hitting_table['H'])) / w_off
    hitting_table['W_SF'] = hitting_table['SF'] / (hitting_table['AB'] - hitting_table['SO'] - hitting_table['H'] + hitting_table['SF'])
    hitting_table['SH_RT'] = hitting_table['SH'] / (hitting_table['AB'] + hitting_table['BB'] + hitting_table['HBP'] + hitting_table['SF'] + hitting_table['SH'])

    #Keep only needed from the hitting table
    hitting_table = hitting_table[['#', 'Player', 'W_AVG', 'W_XBH/H', '%XBH_AS_2B', '%XBH_AS_3B', '%XBH_AS_HR', 'W_K_RT', 'W_BB+_RT', 'W_SB_ATT_RT', 'W_SB%', 'W_GDP', 'W_SF', 'SH_RT']]

    #Defensive adjustments and calculations
    pitching_table['W_BAA'] = pitching_table['B/AVG'] / w_def
    pitching_table['XBHA'] = pitching_table['2B'] + pitching_table['3B'] + pitching_table['HR']
    pitching_table['W_XBH/HA'] = (pitching_table['XBHA'] / pitching_table['H']) / w_def

    pitching_table['%XBH_AS_2BA'] = pitching_table['2B'] / pitching_table['XBHA']
    pitching_table['%XBH_AS_3BA'] = pitching_table['3B'] / pitching_table['XBHA']
    pitching_table['%XBH_AS_HRA'] = pitching_table['HR'] / pitching_table['XBHA']

    pitching_table['W_KA_RT'] = (pitching_table['SO'] / pitching_table['AB']) * w_def
    pitching_table['W_BB+A_RT'] = ((pitching_table['BB'] + pitching_table['HBP']) / (pitching_table['AB'] + pitching_table['BB'] + pitching_table['HBP'] + pitching_table['SFA'])) / w_def

    #Keep only needed from the pitching table
    pitching_table = pitching_table[['#', 'Player', 'W_BAA', 'W_XBH/HA', '%XBH_AS_2BA', '%XBH_AS_3BA', '%XBH_AS_HRA', 'W_KA_RT', 'W_BB+A_RT']]

    #Repeat the pitcher for each batter
    pitching_table = pd.concat([pitching_table] * len(hitting_table), ignore_index=True)

    #Probability table
    prob_df = pd.DataFrame()
    prob_df['#'] = hitting_table['#']

    prob_df['P(SACB)'] = hitting_table['SH_RT']
    prob_df['P(BB+)'] = (hitting_table['W_BB+_RT'] + pitching_table['W_BB+A_RT']) / 2

    prob_df['P(H)'] = (hitting_table['W_AVG'] + pitching_table['W_BAA']) / 2
    prob_df['P(XBH | H)'] = (hitting_table['W_XBH/H'] + pitching_table['W_XBH/HA']) / 2
    prob_df['P(2B | XBH)'] = (hitting_table['%XBH_AS_2B'].fillna(0) + pitching_table['%XBH_AS_2BA'].fillna(0)) / 2
    prob_df['P(3B | XBH)'] = (hitting_table['%XBH_AS_3B'].fillna(0) + pitching_table['%XBH_AS_3BA'].fillna(0)) / 2
    prob_df['P(HR | XBH)'] = (hitting_table['%XBH_AS_HR'].fillna(0) + pitching_table['%XBH_AS_HRA'].fillna(0)) / 2

    prob_df['P(K)'] = (hitting_table['W_K_RT'] + pitching_table['W_KA_RT']) / 2
    prob_df['P(IPO)'] = 1 - prob_df['P(H)'] - prob_df['P(K)']
    prob_df['P(GDP)'] = hitting_table['W_GDP']
    prob_df['P(SF)'] = hitting_table['W_SF']

    prob_df['P(SB_ATT)'] = hitting_table['W_SB_ATT_RT'].fillna(0)
    prob_df['P(SB)'] = hitting_table['W_SB%'].fillna(0)

    #Store game by game results
    game_results = []

    #Snapshot of every play in game 1 (used for the replay)
    game_log = []

    #Names for each PA outcome
    result_names = {'bb_plus': 'Walk / HBP', '1B': 'Single', '2B': 'Double', '3B': 'Triple', 'HR': 'HOME RUN!', 'k': 'Strikeout', 'ipo': 'Out in play', 'gdp': 'Double play', 'sac_b': 'Sacrifice bunt'}

    #Loop for 40 games
    for game_number in range(1, 41):

        #Stat holders for hitters and pitcher
        hitter_box = {}
        for spot in range(1, len(prob_df) + 1):
            hitter_box[spot] = {'#': hitting_table.iloc[spot - 1]['#'], 'PA': 0, 'AB': 0, 'H': 0, '1B': 0, '2B': 0, '3B': 0, 'HR': 0, 'BB+': 0, 'K': 0, 'SACB': 0, 'SF': 0, 'GDP': 0, 'RBI': 0, 'R': 0, 'SB': 0, 'CS': 0}
        pitcher_box = {'IP': 0, 'BF': 0, 'H': 0, 'XBH': 0, 'R': 0, 'HR': 0, 'BB+': 0, 'K': 0}

        #Game start setting
        batter_index = 1
        inning = 1

        #Play 9 innings
        while inning <= 9:

            #Start of inning settings
            out = 0
            first_base = 0
            second_base = 0
            third_base = 0

            #Loop until there are 3 outs
            while out < 3:

                #Get the batter who is up
                spot = (batter_index - 1) % len(prob_df) + 1

                #Stolen base attempt of second (runner on 1st, 2nd base open)
                if first_base != 0 and second_base == 0:
                    runner = first_base
                    if random.random() < prob_df.iloc[runner - 1]['P(SB_ATT)']:
                        if random.random() < prob_df.iloc[runner - 1]['P(SB)']:
                            hitter_box[runner]['SB'] += 1
                            second_base = runner
                        else:
                            hitter_box[runner]['CS'] += 1
                            out += 1
                        first_base = 0

                #Stolen base attempt of third (runner on 2nd, 1st and 3rd open)
                elif second_base != 0 and first_base == 0 and third_base == 0:
                    runner = second_base
                    if random.random() < prob_df.iloc[runner - 1]['P(SB_ATT)']:
                        if random.random() < prob_df.iloc[runner - 1]['P(SB)']:
                            hitter_box[runner]['SB'] += 1
                            third_base = runner
                        else:
                            hitter_box[runner]['CS'] += 1
                            out += 1
                        second_base = 0

                #If a caught stealing was the third out, the inning ends before the batter bats
                if out >= 3:
                    break

                #Bunt chance multiplier
                bunt_mult = 0

                #Runners on 1st and/or 2nd, and sub 2 outs
                if third_base == 0 and (first_base != 0 or second_base != 0) and out <= 1:
                    if out == 0:
                        bunt_mult = 1
                    elif out == 1:
                        bunt_mult = 0.5

                #Roll for sacrifice bunt first
                if random.random() < prob_df.iloc[spot - 1]['P(SACB)'] * bunt_mult:
                    result = 'sac_b'
                else:
                    result = plate_appearance(prob_df.iloc[spot - 1])

                #Records the PA/BF for the hitter an pitcher
                hitter_box[spot]['PA'] += 1
                pitcher_box['BF'] += 1

                #Runners who score on this play (a list of lineup spots)
                scorers = []

                #BB or HBP
                if result == 'bb_plus':
                    hitter_box[spot]['BB+'] += 1
                    pitcher_box['BB+'] += 1
                    first_base, second_base, third_base, scorers = walk(first_base, second_base, third_base, spot)

                #Single
                elif result == '1B':
                    hitter_box[spot]['AB'] += 1
                    hitter_box[spot]['H'] += 1
                    hitter_box[spot]['1B'] += 1
                    pitcher_box['H'] += 1
                    first_base, second_base, third_base, scorers = advance(first_base, second_base, third_base, spot, 1)

                #Double
                elif result == '2B':
                    hitter_box[spot]['AB'] += 1
                    hitter_box[spot]['H'] += 1
                    hitter_box[spot]['2B'] += 1
                    pitcher_box['H'] += 1
                    pitcher_box['XBH'] += 1
                    first_base, second_base, third_base, scorers = advance(first_base, second_base, third_base, spot, 2)

                #Triple
                elif result == '3B':
                    hitter_box[spot]['AB'] += 1
                    hitter_box[spot]['H'] += 1
                    hitter_box[spot]['3B'] += 1
                    pitcher_box['H'] += 1
                    pitcher_box['XBH'] += 1
                    first_base, second_base, third_base, scorers = advance(first_base, second_base, third_base, spot, 3)

                #Home Run
                elif result == 'HR':
                    hitter_box[spot]['AB'] += 1
                    hitter_box[spot]['H'] += 1
                    hitter_box[spot]['HR'] += 1
                    pitcher_box['H'] += 1
                    pitcher_box['XBH'] += 1
                    pitcher_box['HR'] += 1
                    first_base, second_base, third_base, scorers = advance(first_base, second_base, third_base, spot, 4)

                #Strikeout
                elif result == 'k':
                    out += 1
                    hitter_box[spot]['AB'] += 1
                    hitter_box[spot]['K'] += 1
                    pitcher_box['K'] += 1

                #Check for a Sac Fly on In Play Out
                elif result == 'ipo':
                    if third_base != 0 and out < 2 and random.random() <= prob_df.iloc[spot - 1]['P(SF)']:
                        out += 1
                        hitter_box[spot]['SF'] += 1
                        scorers.append(third_base)
                        third_base = 0

                    #In Play Out
                    else:
                        out += 1
                        hitter_box[spot]['AB'] += 1

                #Ground into a double play (needs a runner on first and less than 2 outs)
                elif result == 'gdp':
                    hitter_box[spot]['AB'] += 1
                    hitter_box[spot]['GDP'] += 1
                    if first_base != 0 and out < 2:
                        out += 2
                        first_base = 0
                    else:
                        out += 1

                #Sac Bunt
                elif result == 'sac_b':
                    out += 1
                    hitter_box[spot]['SACB'] += 1
                    if out < 3:
                        if third_base != 0:
                            scorers.append(third_base)
                        third_base = second_base
                        second_base = first_base
                        first_base = 0

                #Give each runner who scored an R, the batter the RBI, and the pitcher the runs
                for runner in scorers:
                    hitter_box[runner]['R'] += 1
                hitter_box[spot]['RBI'] += len(scorers)
                pitcher_box['R'] += len(scorers)

                #Save a snapshot of the play for the replay (first game only)
                if game_number == 1:

                    #A fly out that scored a run is a sacrifice fly
                    runs_before = game_log[-1]['Runs'] if len(game_log) > 0 else 0
                    play_text = result_names[result]
                    if result == 'ipo' and pitcher_box['R'] > runs_before:
                        play_text = 'Sacrifice fly'

                    #1 means a runner is on that base (the bases are cleared after the third out)
                    bases_now = [int(first_base != 0), int(second_base != 0), int(third_base != 0)]
                    if out >= 3:
                        bases_now = [0, 0, 0]

                    game_log.append({'Inning': inning, 'Outs': out, 'Runs': pitcher_box['R'], 'Bases': bases_now, 'Batter': hitter_names[spot - 1], 'Play': play_text, 'Good': result in ['bb_plus', '1B', '2B', '3B', 'HR']})

                #Go to the next hitter
                batter_index += 1

            #Move to the next inning once the while loop ends (3 outs)
            pitcher_box['IP'] += 1
            inning += 1

        #Hitter stat table
        box_df = pd.DataFrame(hitter_box).T

        #Sum of hitter stats
        totals = box_df.sum()

        #AB, Sac Fly, and total bases from hitters
        ab_against = totals['AB']
        sf_against = totals['SF']
        tb_against = totals['1B'] + 2 * totals['2B'] + 3 * totals['3B'] + 4 * totals['HR']

        #Calculate BAA, OBP against, and SLG against
        baa = round(pitcher_box['H'] / ab_against, 3)
        obpa = round((pitcher_box['H'] + pitcher_box['BB+']) / (ab_against + pitcher_box['BB+'] + sf_against), 3)
        slga = round(tb_against / ab_against, 3)

        game_results.append({'Game': game_number, 'Hitter Stats': box_df.copy(), 'Pitcher Stats': pitcher_box.copy(), 'BAA': baa, 'OBPA': obpa, 'SLGA': slga})

    #40-game average pitching statistics
    pitcher_summary = pd.DataFrame([game['Pitcher Stats'] for game in game_results])

    #95 percent confidence interval multiplier (t value for 40 games)
    t_value = 2.023

    #Rows for the pitcher table (one per stat)
    pitcher_rows = []

    #Counting stats: average, then the confidence interval
    for stat in pitcher_summary.columns:
        stat_mean = pitcher_summary[stat].mean()
        stat_margin = t_value * pitcher_summary[stat].std() / (len(pitcher_summary) ** 0.5)
        pitcher_rows.append({'Stat': stat, 'Average': round(stat_mean, 3), 'CI Low': round(stat_mean - stat_margin, 3), 'CI High': round(stat_mean + stat_margin, 3)})

    #Rate stats: average, then the confidence interval
    for rate in ['BAA', 'OBPA', 'SLGA']:
        rate_values = pd.Series([game[rate] for game in game_results])
        rate_mean = rate_values.mean()
        rate_margin = t_value * rate_values.std() / (len(rate_values) ** 0.5)
        pitcher_rows.append({'Stat': rate, 'Average': round(rate_mean, 3), 'CI Low': round(rate_mean - rate_margin, 3), 'CI High': round(rate_mean + rate_margin, 3)})

    pitcher_table = pd.DataFrame(pitcher_rows)

    #Hitter averages over the 40 games
    hitter_summary = pd.concat([game['Hitter Stats'].drop(columns='#') for game in game_results]).groupby(level=0).mean()
    hitter_summary.insert(0, '#', hitting_table['#'].values)
    hitter_summary.insert(1, 'Player', hitter_names)

    hitter_summary['AVG'] = hitter_summary['H'] / hitter_summary['AB']
    hitter_summary['OBP'] = (hitter_summary['H'] + hitter_summary['BB+']) / hitter_summary['PA']
    hitter_summary['SLG'] = (hitter_summary['1B'] + 2 * hitter_summary['2B'] + 3 * hitter_summary['3B'] + 4 * hitter_summary['HR']) / hitter_summary['AB']

    return {
        'pitcher_name': pitcher_name,
        'pitcher_table': pitcher_table,
        'hitter_table': hitter_summary,
        'game_log': game_log,
        'runs': [game['Pitcher Stats']['R'] for game in game_results],
        'xbh': [game['Pitcher Stats']['XBH'] for game in game_results],
        'k': [game['Pitcher Stats']['K'] for game in game_results]}

#This function draws the 3 histograms
def make_histograms(results):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    plots = [
        (results['runs'], 'Runs Allowed Per Game', 'Runs'),
        (results['xbh'], 'Extra Base Hits Allowed Per Game', 'Extra Base Hits'),
        (results['k'], 'Strikeouts Per Game', 'Strikeouts')]

    for ax, (values, title, label) in zip(axes, plots):
        mean = pd.Series(values).mean()
        sd = pd.Series(values).std()
        ax.hist(values, bins=range(min(values), max(values) + 2), align='left', edgecolor='black')
        ax.axvline(mean, color='red', linewidth=2, label=f'Mean: {mean:.2f}')
        ax.axvline(mean - sd, color='grey', linestyle='dashed', label=f'SD: +/-{sd:.2f}')
        ax.axvline(mean + sd, color='grey', linestyle='dashed')
        ax.set_title(title)
        ax.set_xlabel(label)
        ax.set_ylabel('Number of Games')
        ax.legend()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    fig.suptitle(f"{results['pitcher_name']} Pitching Stats")
    fig.tight_layout()
    return fig


#This function draws the game after play number i (1 is the first play)
def draw_replay_frame(game_log, i, team_name, off_logo, def_logo):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(-3.5, 6.5)
    ax.set_ylim(-1.3, 3.2)
    ax.set_aspect('equal')
    ax.axis('off')

    #This puts a logo on the field, centered at (x, y) with the height given (skipped if there is no logo)
    def show_logo(logo, x, y, height, alpha):
        if logo is None:
            return
        width = height * logo.shape[1] / logo.shape[0]
        ax.imshow(logo, extent=[x - width / 2, x + width / 2, y - height / 2, y + height / 2], alpha=alpha)

    show_logo(off_logo, -3.08, 2.72, 0.85, 1.0)
    show_logo(def_logo, 0, 1, 0.6, 0.5)

    play = game_log[i - 1]

    #Diamond outline
    ax.plot([0, 1, 0, -1, 0], [0, 1, 2, 1, 0], color='saddlebrown', linewidth=3)

    #Bases are gold when a runner is on and white when empty (first, second, third)
    base_x = [1, 0, -1]
    base_y = [1, 2, 1]
    for b in range(3):
        base_color = 'gold' if play['Bases'][b] == 1 else 'white'
        ax.scatter(base_x[b], base_y[b], s=1200, marker='D', color=base_color, edgecolor='black', zorder=3)

    #Home plate
    ax.scatter(0, 0, s=1200, marker='p', color='white', edgecolor='black', zorder=3)

    #Scoreboard
    ax.text(-2.4, 2.6, f"{team_name}   Runs: {play['Runs']}", fontsize=18, fontweight='bold')
    ax.text(-2.4, 2.2, f"Inning {play['Inning']}", fontsize=14)

    #Outs: a red circle for each out
    ax.text(-3.2, 1.7, 'Outs:', fontsize=14)
    for o in range(3):
        out_color = 'red' if o < play['Outs'] else 'lightgrey'
        ax.scatter(-2.2 + o * 0.5, 1.8, s=300, color=out_color, edgecolor='black')

    #What just happened (green for the batter reaching base, red for an out)
    play_color = 'green' if play['Good'] else 'red'
    ax.text(-3.2, 0.3, play['Batter'], fontsize=14)
    ax.text(-3.2, -0.4, play['Play'], fontsize=20, fontweight='bold', color=play_color)

    #Play by play (only the plays from the current inning)
    ax.text(2.2, 2.6, f"Inning {play['Inning']} plays", fontsize=14, fontweight='bold')
    inning_plays = [p for p in game_log[:i] if p['Inning'] == play['Inning']]
    for r in range(len(inning_plays)):
        ax.text(2.2, 2.2 - r * 0.3, f"{inning_plays[r]['Batter']} - {inning_plays[r]['Play']}", fontsize=10)

    #Final score on the last play
    if i == len(game_log):
        ax.text(-3.2, -1.0, f"FINAL: {play['Runs']} runs", fontsize=16, fontweight='bold')

    return fig

#This function makes the Excel file for the download button
def make_excel(hitter_table, pitcher_table):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        hitter_table.to_excel(writer, sheet_name='Hitters', index=False)
        pitcher_table.to_excel(writer, sheet_name='Pitcher', index=False)
    return buffer.getvalue()

#This function makes the hitter table easy to read on the page
def format_hitter_table(hitter_table):
    shown = hitter_table.copy()
    for col in shown.columns:
        if col in ['#', 'Player']:
            continue
        elif col in ['AVG', 'OBP', 'SLG']:
            shown[col] = shown[col].map(lambda x: f'{x:.3f}')
        else:
            shown[col] = shown[col].map(lambda x: f'{x:.1f}')
    return shown

#The page
def main():
    st.set_page_config(page_title='D3 Baseball Sim', layout='wide')
    st.title('D3 Baseball Pitcher vs Lineup Sim')
    st.caption('Pick a lineup and a pitcher and the sim plays 40 games. Team ratings from Massey Ratings (masseyratings.com). '
               f'PrestoSports team stats saved {PRESTO_DATA_DATE}. SIDEARM team stats are refreshed every few hours.')

    #Pick the two teams
    left, right = st.columns(2)
    off_name = left.selectbox('Offense (the lineup)', all_team_names, index=None, placeholder='Choose a team')
    def_name = right.selectbox('Defense (the pitcher)', all_team_names, index=None, placeholder='Choose a team')

    if off_name is None or def_name is None:
        st.info('Choose both teams to continue.')
        return
    if off_name == def_name:
        st.warning('Choose two different teams.')
        return

    #Load the stats
    with st.spinner('Loading team stats...'):
        hitting_table, off_pitching = load_team_stats(off_name)
        def_hitting, pitching_table = load_team_stats(def_name)

    if hitting_table is None or off_pitching is None:
        st.error(f'Could not load stats for {off_name}.')
        return
    if def_hitting is None or pitching_table is None:
        st.error(f'Could not load stats for {def_name}.')
        return

    #Pick the pitcher (from the defense team)
    pitcher_options = [f"#{row['#']} {row['Player']}" for _, row in pitching_table.iterrows()]
    pitcher_choice = st.selectbox(f'{def_name} pitcher', pitcher_options)
    pitcher_num = pitcher_choice.split(' ')[0][1:]

    #Pick the lineup (from the offense team), starting with the hitters who have the most at bats
    st.subheader(f'{off_name} lineup')
    hitter_options = [f"#{row['#']} {row['Player']}" for _, row in hitting_table.iterrows()]
    default_order = hitting_table.sort_values('AB', ascending=False).index.tolist()

    lineup_choices = []
    columns = st.columns(3)
    for spot in range(9):
        default_index = default_order[spot] if spot < len(default_order) else 0
        choice = columns[spot % 3].selectbox(f'Batter {spot + 1}', hitter_options, index=int(default_index), key=f'{off_name}_batter_{spot}')
        lineup_choices.append(choice)

    if len(set(lineup_choices)) < 9:
        st.warning('Each hitter can only be in the lineup once.')
        return

    #Run the sim
    if st.button('Run the sim', type='primary'):
        massey_result = massey_weights(off_name, def_name)
        if massey_result is None:
            st.error('Could not find both teams in the saved Massey ratings.')
            return

        lineup_nums = [choice.split(' ')[0][1:] for choice in lineup_choices]
        hitter_lineup = pd.concat([hitting_table[hitting_table['#'] == num].head(1) for num in lineup_nums], ignore_index=True)
        pitcher_stats = pitching_table[pitching_table['#'] == pitcher_num].head(1)

        with st.spinner('Playing 40 games...'):
            results = simulate(hitter_lineup, pitcher_stats, massey_result[0], massey_result[1])

        results['off_name'] = off_name
        results['def_name'] = def_name
        results['off_logo'] = load_logo(off_name)
        results['def_logo'] = load_logo(def_name)
        st.session_state['results'] = results
        st.session_state['played'] = False

    #Show the results (they stay on the page when the replay slider moves)
    results = st.session_state.get('results')
    if results is None:
        return

    st.header(f"{results['pitcher_name']} vs {results['off_name']}")

        #1. Watch the sim (one button: Play game, then Replay game)
    st.subheader('Replay of game 1')
    total_plays = len(results['game_log'])
    button_label = 'Replay game' if st.session_state.get('played') else 'Play game'
    play_all = st.button(button_label)

    #Two places on the page: the field, and the stats (hidden while the game plays so they can not cover the field)
    frame_spot = st.empty()
    stats_spot = st.empty()

    if play_all:
        stats_spot.empty()
        for n in range(1, total_plays + 1):
            replay_fig = draw_replay_frame(results['game_log'], n, results['off_name'], results['off_logo'], results['def_logo'])
            frame_spot.pyplot(replay_fig)
            plt.close(replay_fig)
            time.sleep(1)
        st.session_state['played'] = True
    else:
        #Before it is played show the first play, afterwards show the final play
        show_play = total_plays if st.session_state.get('played') else 1
        replay_fig = draw_replay_frame(results['game_log'], show_play, results['off_name'], results['off_logo'], results['def_logo'])
        frame_spot.pyplot(replay_fig)
        plt.close(replay_fig)

    #2. See the stats and 3. the histograms (these show once the game is done)
    with stats_spot.container():
        st.subheader('Game average pitching stats (95% confidence intervals)')
        st.dataframe(results['pitcher_table'], hide_index=True, width='stretch')

        st.subheader(f"{results['off_name']} game average hitting stats")
        st.dataframe(format_hitter_table(results['hitter_table']), hide_index=True, width='stretch')

        st.download_button(
            'Download the stats as Excel',
            data=make_excel(results['hitter_table'], results['pitcher_table']),
            file_name=f"{results['off_name']} vs {results['pitcher_name']} Sim Stats.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        st.subheader('Distribution over the 40 games')
        fig = make_histograms(results)
        st.pyplot(fig)
        plt.close(fig)
  
main()
