import pandas as pd

data = pd.read_csv("data/final_dataset.csv")

print("Rows:", data.shape[0])
print("Columns:", data.shape[1])

print("\nColumn Names:\n")

for i, column in enumerate(data.columns, start=1):
    print(f"{i}. {column}") 