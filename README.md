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

- `d3_sim_app.py` – Contains the website interface and connects the simulation to the interactive website
- `base_d3_simulation.py` – Contains the initial simulation code, including statistical calculations, player data collection, and game simulation functions
- `requirements.txt` – Lists the Python libraries required to run the project
- `.gitignore` – Lists files and folders that **aren't needed in the GitHub repository** and should therefore be excluded
- `README.md` – Provides an overview of the project and explains its structure and features
- `massey_names/` - Stores team name data and scripts used for Massey Ratings
  - `massey_names.py` - Script used to collect Massey name format
  - `massey_d3_team_names.csv` - Dataset containing the names
- `site_stats/` - Stores team stats urls
  - `PrestoSports.csv` - For teams using PrestoStats Coach's View
  - `SIDEARM.csv` - For teams using SIDEARM stats

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
