
import pandas as pd
import glob
import os

files = glob.glob("s:/fronthaul_ai/data/throughput-cell-*.dat")
for f in files:
    try:
        cell_id = int(os.path.basename(f).replace("throughput-cell-", "").replace(".dat", ""))
        df = pd.read_csv(f, sep=r'\s+', names=["time", "bits"], nrows=1000)
        print(f"Cell {cell_id}: {df['bits'].sum()} bits (first 1000 rows)")
    except Exception as e:
        print(e)
