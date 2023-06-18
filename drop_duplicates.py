import pandas as pd

# Read the CSV file
df = pd.read_csv('stock_exchange.csv')

# Remove duplicates based on the first column
df = df.drop_duplicates(subset=df.columns[0])

# Write the result back to a CSV file
df.to_csv('stock_exchange.csv', index=False)