import os
import psycopg
import google.generativeai as genai
from pgvector.psycopg import register_vector
import datetime

# Configure GenAI (we reuse the key from env)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# DB Connection String
DB_CONNECTION = "dbname=fireline"

def search_logs(timestamp_str, log_file="mock_service.log", time_window_seconds=60):
    """
    Searches a log file for ERROR lines within a time window around a given timestamp.
    """
    print(f"--- 🛠️ Tool: Running search_logs around {timestamp_str} ---")

    # SDEs must always handle timezones. 'Z' means UTC.
    alert_time = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

    start_time = alert_time - datetime.timedelta(seconds=time_window_seconds / 2)
    end_time = alert_time + datetime.timedelta(seconds=time_window_seconds / 2)

    found_errors = []

    try:
        with open(log_file, 'r') as f:
            for line in f:
                if "ERROR" not in line:
                    continue # Skip lines that aren't errors, this is fast.

                # Try to parse the log line timestamp
                try:
                    log_timestamp_str = line.split('Z')[0]
                    log_time = datetime.datetime.fromisoformat(log_timestamp_str + '+00:00')

                    # Check if the error is within our time window
                    if start_time <= log_time <= end_time:
                        found_errors.append(line.strip())

                except (ValueError, IndexError):
                    # This log line has a malformed date, skip it.
                    continue

    except FileNotFoundError:
        print(f"--- ❌ Tool Error: Log file {log_file} not found. ---")
        return ["ERROR: Log file not found."]

    print(f"--- 🛠️ Tool: Found {len(found_errors)} error(s). ---")
    return found_errors

def search_runbooks(query_text):
    """
    Searches the runbook knowledge base for relevant remediation steps using Vector Search.
    """
    print(f"--- 📚 Tool: Searching runbooks for: '{query_text}' ---")

    try:
        # 1. Turn the query (e.g., "High CPU fix") into a vector using Google
        model_name = "models/text-embedding-004"
        result = genai.embed_content(
            model=model_name,
            content=query_text,
            task_type="retrieval_query"
        )
        query_vector = result['embedding']

        # 2. Search Postgres for the nearest neighbor
        with psycopg.connect(DB_CONNECTION, autocommit=True) as conn:
            register_vector(conn)

            # The <=> operator is "Cosine Distance"
            # LIMIT 1 means "give me the single best match"
            result = conn.execute(
                """
                SELECT content 
                FROM runbook_chunks 
                ORDER BY embedding <=> %s 
                LIMIT 1
                """,
                (query_vector,)
            ).fetchone()

            if result:
                print("--- 📚 Tool: Found relevant runbook entry! ---")
                return result[0] # Return the text content
            else:
                return "No relevant runbooks found."

    except Exception as e:
        print(f"--- ❌ Tool Error: {e} ---")
        return f"Error searching runbooks: {e}"
