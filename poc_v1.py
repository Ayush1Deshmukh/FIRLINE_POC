import os
import json
from openai import OpenAI
from dotenv import load_dotenv
# Import our custom tool function from the 'src' package
from src.tools import search_logs
from src.notifications import post_to_slack

# --- 1. SETUP ---
# Load environment variables from .env file (OPENAI_API_KEY)
load_dotenv()

# Initialize the OpenAI client
# It will automatically find the OPENAI_API_KEY in your environment.
try:
    client = OpenAI()
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    print("Please make sure your OPENAI_API_KEY is set correctly in the .env file.")
    exit(1) # Exit the script with an error code

# --- 2. DEFINE THE "TOOLS" FOR THE LLM ---
# This is a "JSON Schema" definition. It's how we describe our
# Python function (search_logs) to the LLM in a language it understands.
tools_definition = [
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Searches a log file for ERROR lines within a time window around a specific timestamp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timestamp_str": {
                        "type": "string",
                        "description": "The ISO 8601 timestamp string for the center of the search window (e.g., '2025-10-21T03:05:00Z')."
                    },
                    "log_file": {
                        "type": "string",
                        "description": "The path to the log file to search."
                    },
                    "time_window_seconds": {
                        "type": "integer",
                        "description": "The total number of seconds for the search window (e.g., 60 means 30s before and 30s after the timestamp)."
                    }
                },
                "required": ["timestamp_str", "log_file"]
            }
        }
    }
]

# --- 3. DEFINE THE AGENT'S "PERSONALITY" AND TASK ---
# The system prompt sets the context, role, and rules for the LLM.
SYSTEM_PROMPT = """
You are "Fireline-01", an autonomous SRE incident investigation agent.
Your sole purpose is to investigate alerts by using the tools provided.
You will be given an alert as a JSON object.

Follow these steps:
1. Analyze the alert.
2. Select the *best* tool to investigate the alert (e.g., `search_logs`).
3. Call the tool with the *exact* parameters derived from the alert.
4. Once you receive the tool's output (e.g., log lines), analyze them.
5. Provide a concise, final summary of your findings and a root cause hypothesis.
6. Do NOT make up information. Base your summary *only* on the tool's output.
"""

# --- 4. THE MAIN ORCHESTRATION FUNCTION ---
def run_investigation():
    print("--- 🔥 Fireline Investigation Started ---")

    # 1. Load the mock alert
    try:
        with open("mock_alert.json", 'r') as f:
            alert = json.load(f)
        print(f"--- 📥 Received Alert: {alert['error_message']} for {alert['service']} ---")
    except FileNotFoundError:
        print("Error: mock_alert.json not found. Please run Step 5 again.")
        return
    except json.JSONDecodeError:
        print("Error: mock_alert.json contains invalid JSON.")
        return

    # We will build our conversation history in this list
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"New Incident Alert: {json.dumps(alert)}"}
    ]

    # --- First LLM Call: Get the tool to use ---
    print("--- 🧠 Agent: Analyzing alert and selecting tool... ---")
    response = client.chat.completions.create(
        model="gpt-4o", # You can also use gpt-4-turbo or gpt-3.5-turbo
        messages=messages,
        tools=tools_definition,
        tool_choice="auto" # Let the model decide which tool to call
    )

    response_message = response.choices[0].message
    messages.append(response_message) # Add the AI's response to our history

    # --- 2. Check if the LLM wants to use a tool ---
    if not response_message.tool_calls:
        print("--- 🧠 Agent: Did not select a tool. Providing analysis instead: ---")
        print(response_message.content)
        return

    tool_call = response_message.tool_calls[0]
    function_name = tool_call.function.name

    if function_name == "search_logs":
        print(f"--- 🧠 Agent: Decided to call `{function_name}` tool. ---")

        # 3. Call the *actual* Python function
        # The LLM gives us the arguments as a JSON string
        function_args = json.loads(tool_call.function.arguments)

        # This is where the magic happens: we execute our local code.
        tool_output = search_logs(
            timestamp_str=function_args.get("timestamp_str"),
            log_file=function_args.get("log_file", "mock_service.log"), # Use default if not provided
            time_window_seconds=function_args.get("time_window_seconds", 60)
        )

        # 4. Send the tool's results back to the LLM
        print("--- 🧠 Agent: Sending tool output back to LLM for final analysis... ---")

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(tool_output) # Convert Python list to JSON string
            }
        )

        # --- Second LLM Call: Get the final summary ---
        final_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
            # No 'tools' parameter here, as we want a text answer
        )

        final_summary = final_response.choices[0].message.content
        print("--- ✅ Investigation Complete. Final Summary: ---")
        print(final_summary)
        # --- 5. POST THE FINAL SUMMARY TO SLACK ---
    if final_summary:
        post_to_slack(final_summary)

    else:
        print(f"--- ❌ Agent: Tried to call an unknown tool: {function_name} ---")

# This is the standard Python way to make a script runnable
if __name__ == "__main__":
    run_investigation()
