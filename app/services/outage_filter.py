import pandas as pd
import jdatetime
from datetime import timedelta


def convert_jalali_datetime_to_gregorian(datetime_str):
    try:
        j_date = jdatetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return j_date.togregorian()
    except Exception:
        return pd.NaT


def filter_outages_by_date(df, start_date, end_date, date_column):
    try:
        df = df.copy()

        df["_filter_time"] = df[date_column].astype(str).apply(convert_jalali_datetime_to_gregorian)

        df = df.dropna(subset=["_filter_time"])

        end_date_next_day = end_date + timedelta(days=1)

        filtered_df = df[
            (df["_filter_time"] >= start_date) &
            (df["_filter_time"] < end_date_next_day)
        ]

        filtered_df = filtered_df.drop(columns=["_filter_time"])

        return filtered_df

    except Exception as e:
        raise ValueError(f"Error filtering outages by date: {e}") from e
