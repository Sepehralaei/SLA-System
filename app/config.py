DB_SETTINGS = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "127.0.0.1,1433",         
    "database": "SLA",
}

CONNECTION_STRING = (
    f"DRIVER={DB_SETTINGS['driver']};"
    f"SERVER={DB_SETTINGS['server']};"
    f"DATABASE={DB_SETTINGS['database']};"
    f"Trusted_Connection=yes;"
    f"Encrypt=no;"
)
