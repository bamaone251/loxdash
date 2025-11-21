from __future__ import annotations
import os, json, sqlite3, datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, g

# ---------- Config ----------
DB_PATH = os.path.join(os.path.dirname(__file__), "database.sqlite3")

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- DB Helpers ----------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS load_maps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        title TEXT NOT NULL,
        run_number TEXT,
        trailer_number TEXT,
        door TEXT,
        fuel_level TEXT,
        driver_name TEXT,
        loader_name TEXT,
        loaded_temp TEXT,
        wol_olpn_count INTEGER,
        stops_json TEXT NOT NULL,          -- [{stop:1, loader:"", driver:""}, ...]
        pallets_json TEXT NOT NULL,        -- 30 items: [{pos:1, row:1, col:1, type:"Frozen|Chiller|Ambient|Eggs|Bread|DP|Flower|Equip", store:"", zone:"F|C|A|E|B|DP|FL|..."}]
        bulkheads_json TEXT NOT NULL,      -- list of indices where bulkheads between pallets are placed (0..15 for row splits); simple integer markers
        plbs_loaded INTEGER DEFAULT 0,
        plbs_created INTEGER DEFAULT 0,
        dpr_rebuilds INTEGER DEFAULT 0,
        dpr_rewraps INTEGER DEFAULT 0,
        dpr_consolidations INTEGER DEFAULT 0,
        loader_notes TEXT,
        driver_notes TEXT,
        sanitary_q1 INTEGER DEFAULT NULL,
        sanitary_q2 INTEGER DEFAULT NULL,
        sanitary_q3 INTEGER DEFAULT NULL,
        sanitary_q4 INTEGER DEFAULT NULL,
        totals_json TEXT NOT NULL          -- {"frozen":0,"chiller":0,"ambient":0,"eggs":0,"bread":0,"dp":0,"flower":0,"equip":0,"total":0}
    );
    """)
    db.commit()

# Ensure DB exists on startup
with app.app_context():
    init_db()

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health")
def health():
    return jsonify({"status":"ok","time": datetime.datetime.utcnow().isoformat()+"Z"})

def row_to_dict(row):
    d = dict(row)
    # Parse JSON fields
    for k in ("stops_json","pallets_json","bulkheads_json","totals_json"):
        if d.get(k):
            d[k] = json.loads(d[k])
    return d

@app.route("/api/loadmaps", methods=["GET","POST"])
def loadmaps():
    db = get_db()
    if request.method == "POST":
        payload = request.get_json(force=True)
        now = datetime.datetime.utcnow().isoformat()+"Z"
        db.execute("""
            INSERT INTO load_maps
            (created_at, updated_at, title, run_number, trailer_number, door, fuel_level,
             driver_name, loader_name, loaded_temp, wol_olpn_count, stops_json, pallets_json,
             bulkheads_json, plbs_loaded, plbs_created, dpr_rebuilds, dpr_rewraps,
             dpr_consolidations, loader_notes, driver_notes, sanitary_q1, sanitary_q2,
             sanitary_q3, sanitary_q4, totals_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now, now,
            payload.get("title","New Load Map"),
            payload.get("run_number"), payload.get("trailer_number"), payload.get("door"),
            payload.get("fuel_level"), payload.get("driver_name"), payload.get("loader_name"),
            payload.get("loaded_temp"), payload.get("wol_olpn_count", 0),
            json.dumps(payload.get("stops_json", [])),
            json.dumps(payload.get("pallets_json", [])),
            json.dumps(payload.get("bulkheads_json", [])),
            payload.get("plbs_loaded", 0), payload.get("plbs_created", 0),
            payload.get("dpr_rebuilds", 0), payload.get("dpr_rewraps", 0),
            payload.get("dpr_consolidations", 0),
            payload.get("loader_notes",""), payload.get("driver_notes",""),
            payload.get("sanitary_q1"), payload.get("sanitary_q2"), payload.get("sanitary_q3"),
            payload.get("sanitary_q4"),
            json.dumps(payload.get("totals_json", {}))
        ))
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        row = db.execute("SELECT * FROM load_maps WHERE id = ?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201

    # GET (list)
    q = request.args.get("q","").strip()
    sql = "SELECT * FROM load_maps"
    params = []
    if q:
        sql += " WHERE title LIKE ? OR run_number LIKE ? OR trailer_number LIKE ?"
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY updated_at DESC"
    rows = db.execute(sql, params).fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/api/loadmaps/<int:lid>", methods=["GET","PUT","DELETE"])
def loadmap_detail(lid: int):
    db = get_db()
    if request.method == "GET":
        row = db.execute("SELECT * FROM load_maps WHERE id = ?", (lid,)).fetchone()
        if not row: 
            return jsonify({"error":"Not found"}), 404
        return jsonify(row_to_dict(row))

    if request.method == "PUT":
        payload = request.get_json(force=True)
        now = datetime.datetime.utcnow().isoformat()+"Z"
        # Build dynamic update for JSON fields
        fields = ["title","run_number","trailer_number","door","fuel_level","driver_name","loader_name",
                  "loaded_temp","wol_olpn_count","plbs_loaded","plbs_created","dpr_rebuilds","dpr_rewraps",
                  "dpr_consolidations","loader_notes","driver_notes","sanitary_q1","sanitary_q2","sanitary_q3","sanitary_q4"]
        json_fields = ["stops_json","pallets_json","bulkheads_json","totals_json"]
        sets = ["updated_at = ?"]
        params = [now]
        for f in fields:
            if f in payload:
                sets.append(f"{f} = ?")
                params.append(payload.get(f))
        for jf in json_fields:
            if jf in payload:
                sets.append(f"{jf} = ?")
                params.append(json.dumps(payload.get(jf)))
        params.append(lid)
        db.execute(f"UPDATE load_maps SET {', '.join(sets)} WHERE id = ?", params)
        db.commit()
        row = db.execute("SELECT * FROM load_maps WHERE id = ?", (lid,)).fetchone()
        if not row: 
            return jsonify({"error":"Not found"}), 404
        return jsonify(row_to_dict(row))

    # DELETE
    db.execute("DELETE FROM load_maps WHERE id = ?", (lid,))
    db.commit()
    return jsonify({"ok": True})

# Serve favicon if needed
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5501"))
    app.run(host="0.0.0.0", port=port, debug=True)
