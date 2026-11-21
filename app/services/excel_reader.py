import pandas as pd

def read_excel(file_path: str):
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    return df