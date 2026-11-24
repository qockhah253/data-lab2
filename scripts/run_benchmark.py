"""Run every experiment sequentially (each in its own process) and delete scratch DBs of the ablations."""
import os, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
DB = HERE.parent / "data" / "db"
PY = sys.executable

A = "load_rowbyrow.py"
B = "load_batch.py"
SAMPLE = "500000"

EXPERIMENTS = [
    # name, script, args, keep_db
    # 1) full data (20.3M trips rows + 20.3M trip_fares rows)
    ("full_B_batch",              B, ["--batch-size", "100000"], True),
    ("full_A_rowbyrow",           A, ["--commit-every", "0"], True),
    # 2) per-row commit: far too slow for the full set -> measured on a small sample, extrapolated in the report
    ("sample10k_A_commit_each_row",   A, ["--commit-every", "1", "--max-rows", "10000"], False),
    ("sample10k_A_commit_each_1000",  A, ["--commit-every", "1000", "--max-rows", "10000"], False),
    # 3) ablation on 500k rows: what exactly makes batch faster?
    ("abl500k_A_rowbyrow",          A, ["--commit-every", "0", "--max-rows", SAMPLE], False),
    ("abl500k_B_untuned_bs100k",    B, ["--no-tune", "--batch-size", "100000", "--max-rows", SAMPLE], False),
    ("abl500k_B_tuned_bs100k",      B, ["--batch-size", "100000", "--max-rows", SAMPLE], False),
    ("abl500k_B_tuned_bs1k",        B, ["--batch-size", "1000", "--max-rows", SAMPLE], False),
    ("abl500k_B_tuned_bs10k",       B, ["--batch-size", "10000", "--max-rows", SAMPLE], False),
]

only = sys.argv[1:]
for name, script, args, keep in EXPERIMENTS:
    if only and name not in only:
        continue
    print(f"=== {name}", flush=True)
    subprocess.run([PY, str(HERE / script), "--name", name, *args], check=True)
    if not keep:
        p = DB / f"{name}.db"
        if p.exists():
            os.remove(p)
