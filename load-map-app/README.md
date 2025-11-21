# Mobile-Friendly Load Map (ALDI-style)

A lightweight Flask app to create, edit, and view mobile-friendly Load Maps for trailers (30 pallet positions, 2x15).

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# Open http://localhost:5959
```

## Notes
- Data is stored locally in `database.sqlite3`. No login/auth.
- Click a pallet to edit its details (Store #, Type, Zone). Long-press to mark/delete.
- Tap the "Print / Save PDF" button to generate a printable load map.
- Optimized for mobile use (big tap targets, sticky action bar).
