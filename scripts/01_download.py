"""Download NYC TLC Yellow Taxi parquet files (2024-01..2024-06) + zone lookup, convert trips to CSV."""
import sys, urllib.request, pathlib
import pyarrow.parquet as pq, pyarrow.csv as pacsv

BASE = "https://d37ci6vzurychx.cloudfront.net"
ROOT = pathlib.Path(__file__).resolve().parent.parent / "data"
RAW = ROOT / "raw"; CSV = ROOT / "csv"
RAW.mkdir(parents=True, exist_ok=True); CSV.mkdir(parents=True, exist_ok=True)
MONTHS = [f"2024-{m:02d}" for m in range(1, 7)]

def fetch(url, dest):
    if dest.exists(): return
    print("download", url, flush=True)
    urllib.request.urlretrieve(url, dest)

fetch(f"{BASE}/misc/taxi_zone_lookup.csv", CSV / "taxi_zone_lookup.csv")
for m in MONTHS:
    p = RAW / f"yellow_tripdata_{m}.parquet"
    fetch(f"{BASE}/trip-data/yellow_tripdata_{m}.parquet", p)
    out = CSV / f"yellow_tripdata_{m}.csv"
    if not out.exists():
        pf = pq.ParquetFile(p)
        with pacsv.CSVWriter(out, pf.schema_arrow) as w:
            for b in pf.iter_batches(batch_size=500_000):
                w.write_batch(b)
        print("csv", out.name, pf.metadata.num_rows, "rows", flush=True)
