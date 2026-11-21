# database_service.py
import pandas as pd

def get_data_from_sql(conn, query: str):
    try:
        df = pd.read_sql(query, conn)
        print("Connected to DB successfully using pyodbc")
        return df
    except Exception as e:
        print(f"Error details: {e}")
        return None

# app/services/database_service.py


def get_recent_uploads(conn, limit: int = 5) -> list[dict]:
    limit = max(1, min(int(limit), 50))

    query = f"""
        SELECT TOP ({limit})
            id,
            filename,
            uploaded_by,
            data_start_date,
            data_end_date,
            record_count,
            created_at
        FROM dbo.UploadLogs
        ORDER BY created_at DESC, id DESC
    """

    cursor = conn.cursor()

    try:
        cursor.execute(query)

        return [
            {
                "id": row.id,
                "filename": row.filename,
                "uploaded_by": row.uploaded_by,
                "data_start_date": row.data_start_date,
                "data_end_date": row.data_end_date,
                "record_count": row.record_count,
                "created_at": row.created_at,
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def file_was_uploaded(conn, file_hash: str) -> bool:
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT TOP (1) 1
            FROM dbo.UploadLogs
            WHERE file_hash = ?
            """,
            file_hash,
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def log_upload_history(
    conn,
    filename: str,
    file_hash: str,
    uploaded_by: str,
    data_start_date: str | None,
    data_end_date: str | None,
    record_count: int,
) -> None:
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO dbo.UploadLogs (
                filename,
                file_hash,
                uploaded_by,
                data_start_date,
                data_end_date,
                record_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            filename,
            file_hash,
            uploaded_by,
            data_start_date,
            data_end_date,
            int(record_count),
        )
    finally:
        cursor.close()

