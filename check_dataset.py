import pandas as pd

data = pd.read_csv("data/smart_agriculture_master_dataset_20000.csv")

print("=" * 60)
print("SMART AGRICULTURE MASTER DATASET")
print("=" * 60)

print("\nRows :", data.shape[0])
print("Columns :", data.shape[1])

print("\nColumn Names\n")

for i, column in enumerate(data.columns, start=1):
    print(f"{i}. {column}")

print("\nMissing Values\n")
print(data.isnull().sum())

print("\nFirst 5 Rows\n")
print(data.head())