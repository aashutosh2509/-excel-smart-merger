import pandas as pd
df = pd.DataFrame({'Sr No': [1, 2, 3], 'Name': ['A', 'B', 'C']})
df['Sr No'] = range(1, len(df) + 1)
print(df)
