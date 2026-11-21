#Imports
import pandas as pd
import requests
from io import StringIO, BytesIO
import os 
from playwright.sync_api import sync_playwright  #type: ignore 
from math import exp
import random
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.animation import FuncAnimation
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import shutil

#This function asks the user for the number of the pitcher
def pitcher_pick():
    p_num = input('Enter the number of the pitcher: ').strip()
    return p_num

#This function asks the user to create a lineup
def lineup_pick(hitting_table):
    lineup = []
    for i in range(1, 10):
        while True:
            try:
                batter = str(input(f'Enter the number of batter {i}: ')).strip()

                #This line raises an IndexError if the number is not on the roster
                hitting_table[hitting_table['#'] == batter]['Player'].iloc[0]

                #Do not allow the same hitter twice
                if batter in lineup:
                    print('That batter is already in the lineup. Try again.')
                else:
                    break

            except IndexError:
                print('That number is not on the hitting roster. Try again.')

        lineup.append(batter)
    return lineup

#This function finds the offensive and defensive weights of the teams input (keep_file is True if the user wants the download saved)
def massey_weights(off_team, def_team, keep_file):

    #The download is saved here while the sim runs
    path = '/Users/owner/Desktop/massey_ratings.csv'

    try:
        #Opens Chrome (placed off the screen) and navigates to the Massey site
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            page = browser.new_page(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1440, 'height': 1000}
            )
            page.goto('https://masseyratings.com/cbase/ncaad3/ratings', wait_until='domcontentloaded', timeout=100000)
            page.wait_for_timeout(8000) #Often needs a long load time

            #Finds the dropdown at the top of Massey's site labeled More and the Export option in it
            selects = page.locator('select')
            dropdown = None

            for i in range(selects.count()):
                current = selects.nth(i)
                options = current.locator('option').all_text_contents()

                if any('More' in option for option in options):
                    dropdown = current
                    break

            if dropdown is None:
                raise Exception('Massey Export dropdown not found.')

            with page.expect_download(timeout=60000) as download_info:
                dropdown.select_option(label='Export')

            #Downloads and saves to the user's desktop
            download_info.value.save_as(path)

            #Closes the Chrome window
            browser.close()

        #Read in the data set
        massey_data = pd.read_csv(path)

        #Finds the matches for the input offensive and defensive teams
        match_off = massey_data[massey_data.iloc[:, 0].astype(str).str.lower().str.strip() == off_team.lower()]
        match_def = massey_data[massey_data.iloc[:, 0].astype(str).str.lower().str.strip() == def_team.lower()]

        #If the offensive name does not match Massey's notation return this message
        if match_off.empty:
            return None

        #If the deffensive name does not match Massey's notation
        if match_def.empty:
            return None

        # Find which column number is for the offensive and defensive rankings
        off_position = massey_data.columns.get_loc("Off")
        def_position = massey_data.columns.get_loc("Def")

        #Gets the offensive and defensive ratings
        off_rating = float(match_off.iloc[:, off_position + 1].item())
        def_rating = float(match_def.iloc[:, def_position + 1].item())

        #Find standardized defensive and offensive rating index
        off_mean = massey_data['Unnamed: 10'].astype(float).mean()
        def_mean = massey_data['Unnamed: 12'].astype(float).mean()

        off_sd = massey_data['Unnamed: 10'].astype(float).std()
        def_sd = massey_data['Unnamed: 12'].astype(float).std()

        off_index = (off_rating - off_mean) / off_sd
        def_index = (def_rating - def_mean) / def_sd

        #Returns the offensive and defensive rating indicies
        return float(off_index), float(def_index)

    #Handle Massey related errors
    except Exception as e:
        return None

    #Save the file with today's date if the user said yes, otherwise delete it
    finally:
        if os.path.exists(path):
            if keep_file == True:
                os.replace(path, '/Users/owner/Desktop/massey_ratings_' + time.strftime('%Y-%m-%d') + '.csv')
            else:
                os.remove(path)

#This function scrapes the hitting and pitching stats from a team's website (Sidearm Sports only). In theory you only need one of the tables unless you are comparing within a team.
def get_sidearm_stats(url):

    #Ensure the url is in the correct format
    url = url.strip()
    if "https://" not in  url:
        url = "https://" + url

    #Try to extract the hitting an pitching stats (see the except below)
    try:
        headers = {'User-Agent': 'D3-Addict-Analytics (contact: jlalonde@bu.edu)'}
        response = requests.get(url, headers=headers, timeout=10)

        #Raises status error (if there is one)
        response.raise_for_status()

        # Turn every table on the page into a pandas table.
        tables = pd.read_html(StringIO(response.text))

        #Will be used to store player stats
        hitting = None
        pitching = None

        #Loop will find hitting and pitching tables
        for table in tables:

        #Matches the hittings stats
            if "OPS" in table.columns and hitting is None:
                hitting = table

        #Matches the pitching stats
            if "ERA" in table.columns and pitching is None:
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

        # Remove rows with missing jersey numbers
        hitting = hitting.dropna(subset=['#'])
        pitching = pitching.dropna(subset=['#'])

        #Change jersey number to str
        hitting["#"] = hitting["#"].astype(int).astype(str)
        pitching["#"] = pitching["#"].astype(int).astype(str)

        #Put SB and ATT into their own columns and drop the current one for the hitting table
        hitting['SB'] = hitting['SB-ATT'].str.split('-').str[0]
        hitting['SB_ATT'] = hitting['SB-ATT'].str.split('-').str[1] 
        hitting = hitting.drop(columns='SB-ATT')

        #Change SB and SB_ATT to numbers
        hitting['SB'] = hitting['SB'].astype(int)
        hitting['SB_ATT'] = hitting['SB_ATT'].astype(int)

        #Return the two tables
        return hitting, pitching

    #If there was an error it is communicated to the user
    except Exception as e:
        print(f"Couldn't get the stats due to error: {e}")
        return None, None

#This function asks if the user wants the stats exported to Excel (asks again until the answer is y or n)
def ask_export():
    while True:
        answer = input('Export the stats to Excel when the sim finishes? (y/n): ').strip().lower()
        if answer == 'y':
            return True
        elif answer == 'n':
            return False
        print('Please enter y or n.')

#This function finds a team's logo on its Sidearm stats page and returns it as an image (returns None if it cannot get one)
def get_team_logo(url):
    try:
        #Make sure the url is in the correct format
        url = url.strip()
        if 'https://' not in url:
            url = 'https://' + url

        #Download the page
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        #Look for the logo image in the page header
        soup = BeautifulSoup(response.text, 'html.parser')
        logo_tag = soup.select_one('.main-header__logo img')

        #If the header logo is not there, use the page's share image instead
        if logo_tag is not None:
            logo_url = logo_tag.get('src')
        else:
            logo_url = soup.find('meta', property='og:image').get('content')

        #Turn the logo link into a full link
        logo_url = urljoin(url, logo_url)

        #Download the logo
        logo_response = requests.get(logo_url, headers={'User-Agent': 'D3-Addict-Analytics (contact: jlalonde@bu.edu)'}, timeout=10)
        logo_response.raise_for_status()

        #SVG logos have to be turned into a PNG first
        if '.svg' in logo_url.lower():
            import cairosvg
            png_bytes = cairosvg.svg2png(bytestring=logo_response.content, output_height=300)
            return plt.imread(BytesIO(png_bytes), format='png')

        return plt.imread(BytesIO(logo_response.content))

    #If anything goes wrong the replay just runs without the logo
    except Exception as e:
        print(f"Couldn't get the logo due to error: {e}")
        return None        

#This function asks if the user wants to keep the Massey download saved on the Desktop (asks again until the answer is y or n)
def ask_keep_massey():
    while True:
        answer = input('Keep the Massey ratings saved on your Desktop? (y/n): ').strip().lower()
        if answer == 'y':
            return True
        elif answer == 'n':
            return False
        print('Please enter y or n.')

#This function asks if the user wants to watch a live replay of one game (asks again until the answer is y or n)
def ask_replay():
    while True:
        answer = input('Watch a live replay of one simulated game? (y/n): ').strip().lower()
        if answer == 'y':
            return True
        elif answer == 'n':
            return False
        print('Please enter y or n.')

#This function saves the hitters and the pitcher to an Excel file on the Desktop (one sheet each)
def export_stats(hitter_table, pitcher_table, file_name):
    path = '/Users/owner/Desktop/' + file_name + '.xlsx'
    try:
        with pd.ExcelWriter(path) as writer:
            hitter_table.to_excel(writer, sheet_name='Hitters', index=False)
            pitcher_table.to_excel(writer, sheet_name='Pitcher', index=False)
        print(f'Saved to {path}')

    #This happens if the file is already open in Excel
    except PermissionError:
        print('Could not save the file. Close it in Excel and try again.')

    except Exception as e:
        print(f"Couldn't save the file due to error: {e}")

#This function draws an animated replay of one game
def watch_game(game_log, team_name, title, off_logo, def_logo):

    #Milliseconds between plays (lower is faster)
    replay_speed = 1200

    replay_fig, replay_ax = plt.subplots(figsize=(10, 6))
    replay_fig.suptitle(title)

    #This puts a logo on the field, centered at (x, y) with the height given (skipped if there is no logo)
    def show_logo(logo, x, y, height, alpha):
        if logo is None:
            return
        width = height * logo.shape[1] / logo.shape[0]
        replay_ax.imshow(logo, extent=[x - width / 2, x + width / 2, y - height / 2, y + height / 2], alpha=alpha)

    #This draws the game after play number i
    def draw_play(i):
        replay_ax.clear()
        replay_ax.set_xlim(-3.5, 6.5)
        replay_ax.set_ylim(-1.3, 3.2)
        replay_ax.set_aspect('equal')
        replay_ax.axis('off')


        #Offense logo by the scoreboard and the defense logo on the pitcher's mound
        show_logo(off_logo, -3.08, 2.72, 0.85, 1.0)
        show_logo(def_logo, 0, 1, 0.6, 0.5)

        play = game_log[i]

        #Diamond outline
        replay_ax.plot([0, 1, 0, -1, 0], [0, 1, 2, 1, 0], color='saddlebrown', linewidth=3)

        #Bases are gold when a runner is on and white when empty (first, second, third)
        base_x = [1, 0, -1]
        base_y = [1, 2, 1]
        for b in range(3):
            if play['Bases'][b] == 1:
                base_color = 'gold'
            else:
                base_color = 'white'
            replay_ax.scatter(base_x[b], base_y[b], s=1200, marker='D', color=base_color, edgecolor='black', zorder=3)

        #Home plate
        replay_ax.scatter(0, 0, s=1200, marker='p', color='white', edgecolor='black', zorder=3)

        #Scoreboard
        replay_ax.text(-2.4, 2.6, f"{team_name}   Runs: {play['Runs']}", fontsize=18, fontweight='bold')
        replay_ax.text(-2.4, 2.2, f"Inning {play['Inning']}", fontsize=14)

        #Outs: a red circle for each out
        replay_ax.text(-3.2, 1.7, 'Outs:', fontsize=14)
        for o in range(3):
            if o < play['Outs']:
                out_color = 'red'
            else:
                out_color = 'lightgrey'
            replay_ax.scatter(-2.2 + o * 0.5, 1.8, s=300, color=out_color, edgecolor='black')

        #What just happened (green for the batter reaching base, red for an out)
        if play['Good']:
            play_color = 'green'
        else:
            play_color = 'red'
        replay_ax.text(-3.2, 0.3, play['Batter'], fontsize=14)
        replay_ax.text(-3.2, -0.4, play['Play'], fontsize=20, fontweight='bold', color=play_color)

        #Play by play (only the plays from the current inning)
        replay_ax.text(2.2, 2.6, f"Inning {play['Inning']} plays", fontsize=14, fontweight='bold')
        inning_plays = [p for p in game_log[:i + 1] if p['Inning'] == play['Inning']]
        for r in range(len(inning_plays)):
            replay_ax.text(2.2, 2.2 - r * 0.3, f"{inning_plays[r]['Batter']} - {inning_plays[r]['Play']}", fontsize=10)

        #Final score on the last play
        if i == len(game_log) - 1:
            replay_ax.text(-3.2, -1.0, f"FINAL: {play['Runs']} runs", fontsize=16, fontweight='bold')

    #Run the replay and return it (the animation has to be kept in a variable or Python deletes it)
    replay = FuncAnimation(replay_fig, draw_play, frames=len(game_log), interval=replay_speed, repeat=False)
    return replay

#This function will serve to run the sim
def d3_sim(off_name, off_url, def_name, def_url):
    
    #Ask if the user wants to keep the Massey download saved on the Desktop
    keep_choice = ask_keep_massey()

    #Call the Massey rankings function
    massey_result = massey_weights(off_name, def_name, keep_choice)

    #Stop if the ratings could not be found
    if massey_result is None:
        return

    off_weight, def_weight = massey_result

    #Get the hitting table from the offensive team's page
    hitting_table, off_pitching = get_sidearm_stats(off_url)

    #Get the pitching table from the defensive team's page
    def_hitting, pitching_table = get_sidearm_stats(def_url)

    #Stop if either stats page could not be loaded
    if hitting_table is None or pitching_table is None:
        print('Could not load stats: Check the URLs and ensure the team uses Sidearm Stats')
        return

    #Call the pitcher selection function and select only the desired arm from the pitching data if that number exists
    while True:
        try:
            pitcher_num = pitcher_pick()
            pitcher_stats = pitching_table[pitching_table['#'] == pitcher_num]
            pitcher_name = pitcher_stats['Player'].iloc[0]
            break

        #IndexError when the number is not on the roster
        except IndexError:
            print('That number is not on the pitching roster. Try again.')

    #Create lineup based on the sim selection
    hitting_lineup = lineup_pick(hitting_table)
    hitter_lineup = pd.concat([hitting_table[hitting_table['#'] == num] for num in hitting_lineup], ignore_index=True)
    
    #Ask if the user wants the stats exported (asked now so the sim can run without waiting)
    export_choice = ask_export()

    #Ask if the user wants to watch a live replay of one game
    replay_choice = ask_replay()

    #Get both team logos if the user wants the replay
    off_logo = None
    def_logo = None
    if replay_choice == True:
        off_logo = get_team_logo(off_url)
        def_logo = get_team_logo(def_url)

    #Use only the lineup for the calculations from here on
    hitting_table = hitter_lineup.reset_index(drop=True)

    #Save the hitter names in lineup order for the report
    hitter_names = hitting_table['Player'].tolist()

    #Use only the chosen pitcher for the calculations from here on
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

    hitting_table['W_GDP'] = (hitting_table['GDP'] / (hitting_table['AB'] - hitting_table['SO'] - hitting_table['H'])) / w_off #Given the ball is already in play
    hitting_table['W_SF'] = hitting_table['SF'] / (hitting_table['AB'] - hitting_table['SO'] - hitting_table['H'] + hitting_table['SF'])
    hitting_table['SH_RT'] = hitting_table['SH'] / (hitting_table['AB'] + hitting_table['BB'] + hitting_table['HBP'] + hitting_table['SF'] + hitting_table['SH'])

    #Drop columns that are no longer needed from the hitting table
    hitting_table = hitting_table.drop(hitting_table.columns[2:23], axis=1)
    hitting_table = hitting_table.drop(columns='XBH')

    #Defensive adjustments and calculations
    pitching_table['W_BAA'] = pitching_table['B/AVG'] / w_def

    pitching_table['XBHA'] = pitching_table['2B'] + pitching_table['3B'] + pitching_table['HR']

    pitching_table['W_XBH/HA'] = (pitching_table['XBHA'] / pitching_table['H']) / w_def

    pitching_table['%XBH_AS_2BA'] = pitching_table['2B'] / pitching_table['XBHA']
    pitching_table['%XBH_AS_3BA'] = pitching_table['3B'] / pitching_table['XBHA']
    pitching_table['%XBH_AS_HRA'] = pitching_table['HR'] / pitching_table['XBHA']

    pitching_table['W_KA_RT'] = (pitching_table['SO'] / pitching_table['AB']) * w_def
    pitching_table['W_BB+A_RT'] = ((pitching_table['BB'] + pitching_table['HBP']) / (pitching_table['AB'] + pitching_table['BB'] + pitching_table['HBP'] + pitching_table['SFA'])) / w_def

    #Drop columns that are no longer needed from the pitching table
    pitching_table = pitching_table.drop(pitching_table.columns[2:25], axis=1)
    pitching_table = pitching_table.drop(columns='XBHA')

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

    #Single AB
    def individual_PAr(prob_df):
        sac_b = 'No'
        bb_plus = 'No'
        hit = 'No'
        xbh = 'No'
        xbh_type = None
        k = 'No'
        ipo = 'No'
        gdp = 'No'

        bb_plus = 'Yes' if random.random() <= prob_df['P(BB+)'] else 'No'

        if bb_plus == 'No':
            hit = 'Yes' if random.random() <= prob_df['P(H)'] else 'No'

            if hit == 'Yes':
                xbh = 'Yes' if random.random() <= prob_df['P(XBH | H)'] else 'No'
            
                if xbh == 'Yes':
                    xbh_type = random.choices(['2B', '3B', 'HR'], weights=[prob_df['P(2B | XBH)'], prob_df['P(3B | XBH)'], prob_df['P(HR | XBH)']])[0]
                    
            else:
                k = 'Yes' if random.random() <= min(1, prob_df['P(K)'] / (1 - prob_df['P(H)'])) else 'No'
                if k == 'No':
                    ipo = 'Yes'
                    gdp = 'Yes' if random.random() <= prob_df['P(GDP)'] else 'No'

        if sac_b == 'Yes':
            par = 'sac_b'
        elif bb_plus == 'Yes':
            par = 'bb_plus'
        elif hit == 'Yes' and xbh == 'No':
            par = '1B'
        elif xbh == 'Yes':
            par = xbh_type
        elif k == 'Yes':
            par = 'k'
        elif ipo == 'Yes' and gdp == 'Yes':
            par = 'gdp'
        elif ipo == 'Yes':
            par = 'ipo'

        return par

    #Chance that a runner on second scores on a single (otherwise he goes to third)
    second_scores_single = 0.65

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

    #Store game by game results
    game_results = []

    #Snapshot of every play in game 1 (used for the live replay)
    game_log = []

    #Live sim naes for each PA outcome
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
                    result = individual_PAr(prob_df.iloc[spot - 1])

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
                        out += 1 #If the conditions for a gdip are not matched yet the result is chosen, record as an ipo

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

                #Save a snapshot of the play for the live replay (first game only)
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

        #Append the game stats to the list storing all 40
        game_results.append({'Game': game_number, 'Hitter Stats': box_df.copy(), 'Pitcher Stats': pitcher_box.copy(), 'BAA': baa, 'OBPA': obpa, 'SLGA': slga})

    #40-game average pitching statistics
    pitcher_summary = pd.DataFrame([game['Pitcher Stats'] for game in game_results])

    #95 percent confidence interval multiplier (t value for 40 games)
    t_value = 2.023

    print(f'\n{pitcher_name} Game Average Pitching Stats w/ 95% CIs:')

    #Rows for the Excel sheet (one per stat)
    pitcher_rows = []

    #Counting stats: average, then the confidence interval
    for stat in pitcher_summary.columns:
        stat_mean = pitcher_summary[stat].mean()
        stat_margin = t_value * pitcher_summary[stat].std() / (len(pitcher_summary) ** 0.5)
        print(f'{stat}: {stat_mean:.2f} [{stat_mean - stat_margin:.2f}, {stat_mean + stat_margin:.2f}]')
        pitcher_rows.append({'Stat': stat, 'Average': round(stat_mean, 3), 'CI Low': round(stat_mean - stat_margin, 3), 'CI High': round(stat_mean + stat_margin, 3)})

    #Rate stats: average, then the confidence interval
    for rate in ['BAA', 'OBPA', 'SLGA']:
        rate_values = pd.Series([game[rate] for game in game_results])
        rate_mean = rate_values.mean()
        rate_margin = t_value * rate_values.std() / (len(rate_values) ** 0.5)
        print(f'{rate}: {rate_mean:.3f} [{rate_mean - rate_margin:.3f}, {rate_mean + rate_margin:.3f}]')
        pitcher_rows.append({'Stat': rate, 'Average': round(rate_mean, 3), 'CI Low': round(rate_margin * -1 + rate_mean, 3), 'CI High': round(rate_mean + rate_margin, 3)})

    #Turn the rows into a table
    pitcher_table = pd.DataFrame(pitcher_rows)

    hitter_summary = pd.concat([game['Hitter Stats'].drop(columns='#') for game in game_results]).groupby(level=0).mean()

    hitter_summary.insert(0, '#', hitting_table['#'].values)
    hitter_summary.insert(1, 'Player', hitter_names)

    hitter_summary['AVG'] = hitter_summary['H'] / hitter_summary['AB']
    hitter_summary['OBP'] = (hitter_summary['H'] + hitter_summary['BB+']) / hitter_summary['PA']
    hitter_summary['SLG'] = (hitter_summary['1B'] + 2 * hitter_summary['2B'] + 3 * hitter_summary['3B'] + 4 * hitter_summary['HR']) / hitter_summary['AB']

    #Copy of the hitter table with real numbers for the Excel export
    hitter_for_excel = hitter_summary.copy()

    hitter_summary = hitter_summary.round(1)
    hitter_summary[['AVG', 'OBP', 'SLG']] = hitter_summary[['AVG', 'OBP', 'SLG']].round(3)

    for col in hitter_summary.columns:
        if col == '#' or col == 'Player':
            continue
        elif col in ['AVG', 'OBP', 'SLG']:
            hitter_summary[col] = hitter_summary[col].map(lambda x: f'{x:.3f}')
        else:
            hitter_summary[col] = hitter_summary[col].map(lambda x: f'{x:.1f}')

    print(f'\n{off_name} Game Average Hitting Stats:')
    print(hitter_summary.to_string(index=False))

    #Save the stats to Excel if the user said yes
    if export_choice == True:
        export_stats(hitter_for_excel, pitcher_table, f'{off_name} vs {pitcher_name} Sim Stats')

    #Keep or delete the Massey download stats based on the user input
    massey_path = '/Users/owner/Desktop/massey_ratings.csv'
    if os.path.exists(massey_path):
        if keep_choice == True:
            #Save a copy with today's date so there is one file for each day the sim was run
            shutil.copy(massey_path, '/Users/owner/Desktop/massey_ratings_' + time.strftime('%Y-%m-%d') + '.csv')
        else:
            os.remove(massey_path)

    #Pull each game's pitcher stats into lists
    runs_each_game = [game['Pitcher Stats']['R'] for game in game_results]
    xbh_each_game = [game['Pitcher Stats']['XBH'] for game in game_results]
    k_each_game = [game['Pitcher Stats']['K'] for game in game_results]

    #Mean and standard deviation for each stat
    runs_mean = pd.Series(runs_each_game).mean()
    runs_sd = pd.Series(runs_each_game).std()
    xbh_mean = pd.Series(xbh_each_game).mean()
    xbh_sd = pd.Series(xbh_each_game).std()
    k_mean = pd.Series(k_each_game).mean()
    k_sd = pd.Series(k_each_game).std()

    #Make 3 histograms side by side
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    #Runs allowed
    axes[0].hist(runs_each_game, bins=range(min(runs_each_game), max(runs_each_game) + 2), align='left', edgecolor='black')
    axes[0].axvline(runs_mean, color='black', linewidth=2, label=f'Mean: {runs_mean:.2f}')
    axes[0].axvline(runs_mean - runs_sd, color='grey', linestyle='dashed', label=f'SD: +/-{runs_sd:.2f}')
    axes[0].axvline(runs_mean + runs_sd, color='grey', linestyle='dashed')
    axes[0].set_title('Runs Allowed Per Game')
    axes[0].set_xlabel('Runs')
    axes[0].set_ylabel('Number of Games')
    axes[0].legend()

    #Extra base hits allowed
    axes[1].hist(xbh_each_game, bins=range(min(xbh_each_game), max(xbh_each_game) + 2), align='left', edgecolor='black')
    axes[1].axvline(xbh_mean, color='black', linewidth=2, label=f'Mean: {xbh_mean:.2f}')
    axes[1].axvline(xbh_mean - xbh_sd, color='grey', linestyle='dashed', label=f'SD: +/-{xbh_sd:.2f}')
    axes[1].axvline(xbh_mean + xbh_sd, color='grey', linestyle='dashed')
    axes[1].set_title('Extra Base Hits Allowed Per Game')
    axes[1].set_xlabel('Extra Base Hits')
    axes[1].set_ylabel('Number of Games')
    axes[1].legend()

    #Strikeouts
    axes[2].hist(k_each_game, bins=range(min(k_each_game), max(k_each_game) + 2), align='left', edgecolor='black')
    axes[2].axvline(k_mean, color='black', linewidth=2, label=f'Mean: {k_mean:.2f}')
    axes[2].axvline(k_mean - k_sd, color='grey', linestyle='dashed', label=f'+/- SD: +/-{k_sd:.2f}')
    axes[2].axvline(k_mean + k_sd, color='grey', linestyle='dashed')
    axes[2].set_title('Strikeouts Per Game')
    axes[2].set_xlabel('Strikeouts')
    axes[2].set_ylabel('Number of Games')
    axes[2].legend()

    #Force whole number ticks on both axes of every plot
    for ax in axes:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    #Add the pitcher's name as the main title and show the plots
    fig.suptitle(f'{pitcher_name} Pitching Stats')
    plt.tight_layout()

    #Show the live replay if the user selected it
    if replay_choice == True:
        replay = watch_game(game_log, off_name, f'{off_name} vs {pitcher_name} - Game 1 Replay', off_logo, def_logo)

    plt.show()
