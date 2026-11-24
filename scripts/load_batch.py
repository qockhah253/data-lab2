"""Method B - batch: buffer rows, flush with executemany() in big transactions, tuned PRAGMAs,
indexes created AFTER loading (their build time is included in the total)."""
import argparse, os, time
import common as c

ap = argparse.ArgumentParser()
ap.add_argument("--name", required=True)
ap.add_argument("--batch-size", type=int, default=100_000)
ap.add_argument("--max-rows", type=int, default=None)
ap.add_argument("--no-tune", action="store_true", help="keep default PRAGMAs (isolates batching effect)")
a = ap.parse_args()

db = str(c.DB_DIR / f"{a.name}.db")
pragmas = [] if a.no_tune else ["PRAGMA journal_mode=OFF", "PRAGMA synchronous=OFF",
                                "PRAGMA locking_mode=EXCLUSIVE", "PRAGMA cache_size=-400000",
                                "PRAGMA temp_store=MEMORY"]
conn = c.create_db(db, pragmas)
c.load_dimensions(conn)
cur = conn.cursor()

trips, fares = [], []


def flush():
    cur.executemany(c.INSERT_TRIP, trips)
    cur.executemany(c.INSERT_FARE, fares)
    trips.clear()
    fares.clear()


t0 = time.perf_counter()
tid = 0
last_file = 0
for fi, row in c.iter_rows(a.max_rows):
    if fi != last_file:
        flush()
        conn.commit()
        last_file = fi
    tid += 1
    t, f = c.parse(row, tid)
    trips.append(t)
    fares.append(f)
    if len(trips) >= a.batch_size:
        flush()
flush()
conn.commit()
t_load = time.perf_counter() - t0
for ddl in c.INDEXES:
    conn.execute(ddl)
conn.commit()
secs = time.perf_counter() - t0
conn.close()
c.save_result(a.name, {"method": "batch-executemany", "batch_size": a.batch_size, "tuned": not a.no_tune,
                       "rows": tid, "load_seconds": round(t_load, 2), "seconds": round(secs, 2),
                       "rows_per_sec": round(tid / secs), "db_mb": round(os.path.getsize(db) / 1e6)})
