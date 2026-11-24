"""Method A - row-by-row: one cursor.execute() per row per table, default SQLite settings,
indexes created BEFORE loading. --commit-every N controls transaction size
(1 = commit after every trip, 0 = one commit per CSV file)."""
import argparse, os, time
import common as c

ap = argparse.ArgumentParser()
ap.add_argument("--name", required=True)
ap.add_argument("--commit-every", type=int, default=0)
ap.add_argument("--max-rows", type=int, default=None)
a = ap.parse_args()

db = str(c.DB_DIR / f"{a.name}.db")
conn = c.create_db(db)          # default pragmas: journal=DELETE, synchronous=FULL
c.load_dimensions(conn)
for ddl in c.INDEXES:           # indexes exist while inserting (typical naive setup)
    conn.execute(ddl)
cur = conn.cursor()

t0 = time.perf_counter()
tid = 0
last_file = 0
for fi, row in c.iter_rows(a.max_rows):
    if fi != last_file:         # file boundary -> commit
        conn.commit()
        last_file = fi
    tid += 1
    trip, fare = c.parse(row, tid)
    cur.execute(c.INSERT_TRIP, trip)
    cur.execute(c.INSERT_FARE, fare)
    if a.commit_every and tid % a.commit_every == 0:
        conn.commit()
conn.commit()
secs = time.perf_counter() - t0
conn.close()
c.save_result(a.name, {"method": "row-by-row", "commit_every": a.commit_every, "rows": tid,
                       "seconds": round(secs, 2), "rows_per_sec": round(tid / secs),
                       "db_mb": round(os.path.getsize(db) / 1e6)})
