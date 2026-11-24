"""Shared pieces: schema, dimension seed data, CSV row parsing, result recording."""
import csv, glob, json, os, sqlite3, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_DIR = ROOT / "data" / "csv"
DB_DIR = ROOT / "data" / "db"
RESULTS_DIR = ROOT / "results"

SCHEMA = """
CREATE TABLE vendors        (vendor_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE rate_codes     (rate_code_id INTEGER PRIMARY KEY, description TEXT NOT NULL);
CREATE TABLE payment_types  (payment_type_id INTEGER PRIMARY KEY, description TEXT NOT NULL);
CREATE TABLE zones          (location_id INTEGER PRIMARY KEY, borough TEXT, zone TEXT, service_zone TEXT);
CREATE TABLE trips (
    trip_id          INTEGER PRIMARY KEY,
    vendor_id        INTEGER REFERENCES vendors(vendor_id),
    pickup_ts        TEXT NOT NULL,
    dropoff_ts       TEXT NOT NULL,
    passenger_count  INTEGER,
    trip_distance    REAL,
    rate_code_id     INTEGER REFERENCES rate_codes(rate_code_id),
    store_and_fwd    TEXT,
    pu_location_id   INTEGER REFERENCES zones(location_id),
    do_location_id   INTEGER REFERENCES zones(location_id),
    payment_type_id  INTEGER REFERENCES payment_types(payment_type_id)
);
CREATE TABLE trip_fares (
    trip_id               INTEGER PRIMARY KEY REFERENCES trips(trip_id),
    fare_amount           REAL, extra REAL, mta_tax REAL, tip_amount REAL,
    tolls_amount          REAL, improvement_surcharge REAL, total_amount REAL,
    congestion_surcharge  REAL, airport_fee REAL
);
"""
INDEXES = [
    "CREATE INDEX idx_trips_pickup_ts ON trips(pickup_ts)",
    "CREATE INDEX idx_trips_pu ON trips(pu_location_id)",
    "CREATE INDEX idx_trips_do ON trips(do_location_id)",
]
INSERT_TRIP = "INSERT INTO trips VALUES (?,?,?,?,?,?,?,?,?,?,?)"
INSERT_FARE = "INSERT INTO trip_fares VALUES (?,?,?,?,?,?,?,?,?,?)"

VENDORS = {1: "Creative Mobile Technologies", 2: "VeriFone Inc.", 6: "Myle Technologies", 7: "Helix"}
RATE_CODES = {1: "Standard rate", 2: "JFK", 3: "Newark", 4: "Nassau or Westchester",
              5: "Negotiated fare", 6: "Group ride", 99: "Unknown"}
PAYMENT_TYPES = {0: "Flex Fare trip", 1: "Credit card", 2: "Cash", 3: "No charge",
                 4: "Dispute", 5: "Unknown", 6: "Voided trip"}


def csv_files():
    return sorted(glob.glob(str(CSV_DIR / "yellow_tripdata_*.csv")))


def _i(s):
    return int(float(s)) if s else None


def _f(s):
    return float(s) if s else None


def parse(row, trip_id):
    """CSV row (list of str) -> (trips tuple, trip_fares tuple)."""
    trip = (trip_id, _i(row[0]), row[1][:19], row[2][:19], _i(row[3]), _f(row[4]), _i(row[5]),
            row[6], _i(row[7]), _i(row[8]), _i(row[9]))
    fare = (trip_id, _f(row[10]), _f(row[11]), _f(row[12]), _f(row[13]), _f(row[14]),
            _f(row[15]), _f(row[16]), _f(row[17]), _f(row[18]))
    return trip, fare


def iter_rows(max_rows=None):
    """Yield (file_index, csv_row) across all CSV files."""
    n = 0
    for fi, path in enumerate(csv_files()):
        with open(path, newline="") as fh:
            r = csv.reader(fh)
            next(r)  # header
            for row in r:
                yield fi, row
                n += 1
                if max_rows and n >= max_rows:
                    return


def create_db(path, pragmas=()):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    for p in pragmas:
        conn.execute(p)
    conn.executescript(SCHEMA)
    return conn


def load_dimensions(conn):
    """Small lookup tables - identical for every method, not part of the timed section."""
    conn.executemany("INSERT INTO vendors VALUES (?,?)", VENDORS.items())
    conn.executemany("INSERT INTO rate_codes VALUES (?,?)", RATE_CODES.items())
    conn.executemany("INSERT INTO payment_types VALUES (?,?)", PAYMENT_TYPES.items())
    with open(CSV_DIR / "taxi_zone_lookup.csv", newline="") as fh:
        r = csv.reader(fh)
        next(r)
        conn.executemany("INSERT INTO zones VALUES (?,?,?,?)",
                         [(int(a), b, c, d) for a, b, c, d in r])
    conn.commit()


def save_result(name, data):
    RESULTS_DIR.mkdir(exist_ok=True)
    with open(RESULTS_DIR / f"{name}.json", "w") as fh:
        json.dump(data, fh, indent=2)
    print(json.dumps(data))
