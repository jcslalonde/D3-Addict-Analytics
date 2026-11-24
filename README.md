# D3 Addict Analytics

A baseball analytics and simulation project created by Julian LaLonde, designed to simulate hypothetical NCAA Division III baseball matchups between an individual pitcher and an opposing lineup using player statistics weighted by team offensive and defensive strength rankings.

## Overview

D3 Addict Analytics was created to give Division III baseball enthusiasts and coaching staffs an opportunity to explore hypothetical matchups that may otherwise never take place or have limited statistical data available.

This simulation tool takes inputs of a single pitcher, and entire batting lineup, from programs using SIDEARM stats. Team offensive and defensive strength ratings are then pulled from Massey Ratings, standardized to the league, and weighted to the appropriate stats. The simulation looks to find the probability of PA outcomes, and runs 9 inning (one half only, pitcher v lineup) games of this matchup. The simulation runs 40 games, representing the 40 game Division III cap.

After the user is asked to input the two teams, a pitcher, and batting order, these are the following remaining selections (each a yes (y) or no (n) response): 
  1) Save the Massey Ratings of the current day (the day the sim is being run) to the user's device
  2) Export the simulation box scores to an XLSX file on the user's device
  3) View a single live game of the 40 simulations run

The output is composed of 3 sections.
  1) Game average pitcher stats alongside confidence intervals with game average hitting box scores
  2) Histograms of runs per game, extra base hits per game, and strikeouts per game, each with a mean and +/- 1 standard deviation bar
  3) (Optionally) A live view of a play-by-play 9 inning simulated game

## Project Structure

- `d3_sim_app.py` – Contains the website interface and connects the simulation to the interactive website (offense and defense can each be set to the 2025 or 2026 season)
- `base_d3_simulation.py` – Contains the initial simulation code, including statistical calculations, player data collection, and game simulation functions, which was the first draft testing idea built.
- `requirements.txt` – Lists the Python libraries required to run the project
- `.gitignore` – Lists files and folders that **aren't needed in the GitHub repository** and should therefore be excluded
- `README.md` – Provides an overview of the project and explains its structure and features
- `background.jpg` – Ballpark photo used as the website background
- `.streamlit/config.toml` – Website theme settings (light theme)
- `massey_names/` – Stores team name data and scripts used for Massey Ratings
  - `massey_names.py` – Script used to collect Massey name format
  - `massey_d3_team_names.csv` – Dataset containing the names
- `massey_ratings/` – Saved Massey Ratings for each season
  - `massey_ratings_eoy26.csv` – 2026 season ratings
  - `massey_raings_eoy25.csv` – 2025 season ratings
- `site_domains/` – Stores team stats urls for each season
  - `PrestoSports_26.csv` / `PrestoSports_2025.csv` – For teams using PrestoSports Coach's View (2026 and 2025 seasons)
  - `SIDEARM.csv` / `SIDEARM_25.csv` – For teams using SIDEARM stats (2026 and 2025 seasons)
- `presto_stats/` – PrestoSports team stats, saved as text because most of these sites block scripts
  - `presto_text_fn.py` – Reads the saved Coach's View text into hitting and pitching tables
  - `presto_stats_to_txt.py` – Opens each team's Coach's View page so the text can be copied and saved
  - `presto_text_26/` – Saved Coach's View text for each PrestoSports team, 2026 season
  - `presto_text_25/` – Saved Coach's View text for each PrestoSports team, 2025 season
- `presto_logos/` – Team logos for PrestoSports schools
  - `save_logos_from_screenshots.py` – Script used to turn logo screenshots into PNG files
- `sidearm_logos/` – Team logos for SIDEARM schools
  - `save_sidearm_logos.py` – Script used to collect the logos from each team's website

**Seasons:** the 2026 season is the 2025-26 school year, and the 2025 season is 2024-25. The website reads only the files in this repository, except for SIDEARM team stats, which it loads live from each school's site.

## Data Sources & Acknowledgments

**Massey Ratings**
- Source: [Massey Ratings – NCAA Division III Baseball](https://masseyratings.com/cbase/ncaa-d3/ratings)
- Data used: Team offensive and defensive strength ratings
- Author: Ken Massey

**SIDEARM Sports**
- Source: Individual NCAA Division III college athletics statistics pages powered by SIDEARM Sports
- Data used: Individual player hitting and pitching statistics
- Note: Statistics are collected from the respective college athletics websites

*D3 Addict Analytics is an independent project and is not affiliated with or endorsed by Massey Ratings, SIDEARM Sports, or the NCAA
