import pandas as pd

def calculate_outage_per_site(df, site_column='site_name', duration_column='time_delta'):
    try:
        df = df.copy()

        df[duration_column] = pd.to_timedelta(df[duration_column], errors='coerce')

        df = df.dropna(subset=[duration_column])

        result = (
            df.groupby(site_column, as_index=False)[duration_column]
            .sum()
        )

        result['total_seconds'] = result[duration_column].dt.total_seconds()

        return result.sort_values(by='total_seconds', ascending=False)

    except Exception as e:
        raise ValueError(f"Error calculating outage per site: {e}") from e
def calculate_total_outage(df, duration_column="time_delta"):
    try:
        df = df.copy()

        df[duration_column] = pd.to_timedelta(df[duration_column], errors= "coerce")
        df = df.dropna(subset=[duration_column])

        total_duration = df[duration_column].sum()
        total_seconds = total_duration.total_seconds()

        return {
            'total_duration': total_duration,
            "total_seconds" : total_seconds
        }
    except Exception as e:
        raise ValueError(f"Error calculating total outage: {e}") from e