import os
import requests

def post_to_slack(summary):
    """
    Posts a message to a Slack channel using a webhook URL.
    """
    print(f"--- 🚀 Scribe Agent: Posting summary to Slack... ---")

    # 1. Get the webhook URL from the environment variables
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    # 2. SDE Best Practice: Defensive check.
    if not webhook_url:
        print("--- ❌ Scribe Error: SLACK_WEBHOOK_URL is not set. Cannot post. ---")
        print("--- Please check your .env file. ---")
        return

    # 3. Format the message for Slack's API
    # Slack's "Incoming Webhooks" expect a JSON payload with a "text" key.
    # We'll format it nicely using Markdown's "block quote".
    payload = {
        "text": f"🔥 *Fireline Investigation Complete* 🔥\n\n> {summary.replace('\n', '\n> ')}"
    }

    # 4. Make the network request with error handling
    try:
        response = requests.post(webhook_url, json=payload)

        # Check for a successful HTTP status code (e.g., 200)
        if response.status_code == 200:
            print("--- ✅ Scribe Agent: Posted to Slack successfully. ---")
        else:
            # This helps debug if the URL is wrong or Slack is down
            print(f"--- ❌ Scribe Error: Slack returned status code {response.status_code} ---")
            print(f"--- Response: {response.text} ---")

    except requests.exceptions.RequestException as e:
        # This catches network errors (e.g., you're offline)
        print(f"--- ❌ Scribe Error: Network error while posting to Slack: {e} ---")