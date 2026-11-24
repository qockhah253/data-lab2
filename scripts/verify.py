"""Check that both full databases are identical and consistent, and time a few sample queries."""
import json, sqlite3, time, sys
import common as c

NAMES = ["full_A_rowbyrow", "full_B_batch"]
QUERIES = {
    "rows_trips": "SELECT COUNT(*) FROM trips",
    "rows_fares": "SELECT COUNT(*) FROM trip_fares",
    "sum_total": "SELECT ROUND(SUM(total_amount),2) FROM trip_fares",
    "sum_distance": "SELECT ROUND(SUM(trip_distance),2) FROM trips",
    "id_checksum": "SELECT SUM(trip_id), MIN(pickup_ts), MAX(pickup_ts) FROM trips",
    "trips_per_borough": ("SELECT z.borough, COUNT(*), ROUND(AVG(f.total_amount),2) FROM trips t "
                          "JOIN zones z ON z.location_id=t.pu_location_id "
                          "JOIN trip_fares f ON f.trip_id=t.trip_id GROUP BY z.borough ORDER BY 2 DESC"),
    "top_routes": ("SELECT pu.zone, do_.zone, COUNT(*) c FROM trips t "
                   "JOIN zones pu ON pu.location_id=t.pu_location_id "
                   "JOIN zones do_ ON do_.location_id=t.do_location_id "
                   "GROUP BY 1,2 ORDER BY c DESC LIMIT 5"),
    "fk_violations": "SELECT COUNT(*) FROM pragma_foreign_key_check",
}
out = {}
for n in NAMES:
    conn = sqlite3.connect(str(c.DB_DIR / f"{n}.db"))
    out[n] = {}
    for q, sql in QUERIES.items():
        t = time.perf_counter()
        res = conn.execute(sql).fetchall()
        out[n][q] = {"result": res, "seconds": round(time.perf_counter() - t, 2)}
a, b = NAMES
same = all(out[a][q]["result"] == out[b][q]["result"] for q in QUERIES)
out["identical_results"] = same
c.RESULTS_DIR.mkdir(exist_ok=True)
with open(c.RESULTS_DIR / "verify.json", "w") as fh:
    json.dump(out, fh, indent=1)
print("IDENTICAL:", same)
for q in QUERIES:
    print(q, out[a][q]["result"][:6], "| A %.2fs  B %.2fs" % (out[a][q]["seconds"], out[b][q]["seconds"]))
