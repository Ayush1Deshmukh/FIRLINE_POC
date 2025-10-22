import datetime

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