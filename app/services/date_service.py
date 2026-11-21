import jdatetime
from datetime import datetime

def jalali_to_gregorian(date_str):
    try:
        # پاکسازی ورودی
        date_str = date_str.strip()
        date_str = date_str.replace('"', '').replace("'", "")
        date_str = date_str.replace("-", "/")

        parts = date_str.split("/")

        if len(parts) != 3:
            raise ValueError("Date must be YYYY/MM/DD")

        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])

        j_date = jdatetime.date(year, month, day)
        g_date = j_date.togregorian()

        return datetime(g_date.year, g_date.month, g_date.day)

    except Exception as e:
        raise ValueError(f"Invalid Jalali date format: {date_str}") from e
