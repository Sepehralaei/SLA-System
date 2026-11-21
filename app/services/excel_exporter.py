import pandas as pd


def clean_value(x):

    s = str(x)
    s_no_dot = s.replace('.', '', 1)

    if s_no_dot.isdigit():
        return str(int(x))
    else:
        return x


def export_report(df, total_downtime, output_path):
    df_export = df.copy()

    df_export["start_time"] = df_export["start_time"].astype(str)
    df_export["end_time"] = df_export["end_time"].astype(str)

    df_export["start_time"] = df_export["start_time"].apply(clean_value)

    df_export["time_delta"] = df_export["time_delta"].astype(str).str.replace('0 days ', '')

    summary = pd.DataFrame({
        "site_name": ["total downtime"],
        "start_time": [""],
        "end_time": [""],
        "time_delta": [str(total_downtime).replace('0 days ', '')]
    })

    result = pd.concat([df_export, summary])
    result.to_excel(output_path, index=False)
