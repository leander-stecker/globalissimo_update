# Globalissimo – custom country cards

Cards for 196 countries: the 193 UN members plus Palestine, Taiwan and Kosovo.
Data as of November 2026, mostly from 2024/2025.

## Files

| File | What it is |
|---|---|
| `globalissimo_cards_data.csv` | One row per country: ISO3 code, names, capital, board number, status and the 12 card values |
| `globalissimo_value_notes.csv` | Year, source and comment for every value (status: clean, other source or manual estimate) |
| `make_cards.py` | Card generator (Python standard library only) |
| `globalissimo_cards.html` / `.pdf` | All 196 cards, A4, 8 cards per sheet, fronts and backs |
| `flags/` | One flag SVG per ISO2 code |

## Categories (clockwise from 12 o'clock)

Population, area, fertility rate, physicians per 1,000, people per km², GDP per capita,
tourists per year, paved roads, mobile phones per 100, prisoners per 100,000, CO₂ per capita,
highest point. Main sources: World Bank, WHO, UN Tourism, World Prison Brief, Our World in Data,
CIA World Factbook; details per value are in the notes file.

## Making the cards

```
python make_cards.py globalissimo_cards_data.csv                 # English
python make_cards.py globalissimo_cards_data.csv --lang de       # German
python make_cards.py globalissimo_cards_data.csv --only DEU,JPN   # just a few cards
python make_cards.py --download-flags                             # fetch missing flags
```

* The PDF is made with Edge or Chrome (also from WSL). If that fails the script prints
  `PDF step failed`; then open the HTML file and print it at 100 % scale with no margins.
* Cards are ordered by the `board_number` column, the current setup is made by hand roughly geographical.
* With `--lang de` the English capitals are used unless the CSV has a `capital_de` column.
* Card size (63 × 88 mm (MTG size), landscape), layout, colors and fonts are set at the top of `make_cards.py`.
