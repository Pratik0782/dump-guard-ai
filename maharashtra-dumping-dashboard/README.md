# Fieldnotes: Western Maharashtra waste hotspot explorer

A responsive Flask and Bootstrap dashboard for exploring the supplied Kolhapur, Sangli and Satara CSV dataset. The app bundles the CSV in `data/hotspots.csv`, serves browser assets from `public/`, and uses Vercel's Python runtime.

## Important data note

The source file identifies its incident and risk values as synthetic. Locality names are representative, and coordinates are generated around district centres. These records are not verified illegal-dumping incidents. The interface repeats this limitation, including on the map and in the patterns view.

The prediction dropdown uses the village inventory in [data/VILLAGE_DATA.md](data/VILLAGE_DATA.md). Villages without incident records receive a model estimate using available taluka or district profiles, not village-specific history.

## Run locally

Requires Python 3.10 or newer.

```powershell
cd C:\Users\USER\maharashtra-dumping-dashboard
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5051.

## Deploy to Vercel

1. Push this project folder to a Git repository.
2. Import the repository in Vercel and deploy with the included `vercel.json` configuration.
3. Keep `data/hotspots.csv` in the repository; it is read by the serverless function at startup.

The external Bootstrap, Chart.js, Leaflet, font, and OpenStreetMap tile assets require an internet connection in the browser.