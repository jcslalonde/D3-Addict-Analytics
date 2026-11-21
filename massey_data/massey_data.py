#Imports
from pathlib import Path
import pandas as pd
from playwright.sync_api import sync_playwright


#Massey Ratings NCAA Division III baseball data
massey_url = 'https://masseyratings.com/cbase/ncaad3/ratings'

# Save the files in the same folder as this script
output_folder = Path(__file__).resolve().parent
massey_export = output_folder / 'massey_d3_full_export.csv'
team_names_file = output_folder / 'massey_d3_team_names.csv'


def main():
    # Download the full Massey ratings export
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=['--window-position=-3000,-3000'])

        page = browser.new_page()
        page.goto(massey_url, wait_until='domcontentloaded', timeout=100000)
        page.wait_for_timeout(10000)

        dropdown = page.locator('select', has=page.locator('option', has_text='More')).first

        with page.expect_download(timeout=60000) as download_info:
            dropdown.select_option(label='Export')

        download_info.value.save_as(str(massey_export))
        browser.close()

    #Read the Massey export
    massey_data = pd.read_csv(massey_export)

    if massey_data.empty or len(massey_data.columns) == 0:
        raise ValueError('Massey export is empty')

    #Extract the exact names as written
    team_names = (massey_data.iloc[:, 0].dropna().astype(str).str.strip())

    team_names = team_names[team_names.ne('')]
    team_names = team_names.drop_duplicates(keep='first')

    # Save the team names without changing Massey's spelling
    pd.DataFrame({"massey_name": team_names}).to_csv(team_names_file, index=False, encoding='utf-8-sig')


if __name__ == "__main__":
    main()
