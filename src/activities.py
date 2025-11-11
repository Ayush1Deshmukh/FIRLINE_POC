import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from temporalio import activity
# No 'FunctionResponse' import needed, we will use genai.types

# Import our local tools
from src.tools import search_logs
from src.notifications import post_to_slack

# --- 1. SETUP ---
load_dotenv()

# --- Setup Google GenAI Client ---
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found. Did you set it in the .env file?")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    activity.logger.error(f"Error initializing Google GenAI client: {e}")

# --- 2. DEFINE THE "TOOLS" FOR THE LLM ---
search_logs_tool = {
    "name": "search_logs",
    "description": "Searches a log file for ERROR lines within a time window around a specific timestamp.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "timestamp_str": {
                "type": "STRING",
                "description": "The ISO 8601 timestamp string (e.g., '2025-10-21T03:05:00Z')."
            },
            "log_file": {
                "type": "STRING",
                "description": "The path to the log file to search. (Default: mock_service.log)"
            },
            "time_window_seconds": {
                "type": "INTEGER",
                "description": "The total number of seconds for the search window (e.g., 60 means 30s before and 30s after the timestamp)."
            }
        },
        # --- FIX: 'log_file' is now OPTIONAL ---
        "required": ["timestamp_str"] 
    }
}

# --- 3. DEFINE THE AGENT'S "PERSONALITY" AND TASK ---
SYSTEM_PROMPT = """
You are "Fireline-01", an autonomous SRE incident investigation agent.
Your sole purpose is to investigate alerts by using the tools provided.
You will be given an alert as a JSON object.

Follow these steps:
1. Analyze the alert.
2. Select the *best* tool to investigate the alert (e.g., `search_logs`).
3. Call the tool with the *exact* parameters derived from the alert. 
   If you are not given a specific log file path, do not invent one.
4. Once you receive the tool's output (e.g., log lines), analyze them.
5. Provide a concise, final summary of your findings and a root cause hypothesis.
6. Do NOT make up information. Base your summary *only* on the tool's output.
"""

# --- 4. CREATE THE MODEL ---
# We use 'models/gemini-pro-latest' which was on your approved list
model = genai.GenerativeModel(
    model_name='models/gemini-pro-latest',
    system_instruction=SYSTEM_PROMPT,
    tools=[search_logs_tool]
)


# --- 5. THE ACTIVITY DEFINITION ---
@activity.defn
async def run_investigation(alert: dict) -> str:
    activity.logger.info(f"--- 🔥 Fireline Investigation Started for {alert['service']} ---")

    chat = model.start_chat()

    activity.logger.info("--- 🧠 Agent: Analyzing alert and selecting tool... ---")

    user_prompt = f"New Incident Alert: {json.dumps(alert)}"

    try:
        response = await chat.send_message_async(user_prompt)

        response_message = response.candidates[0].content

        if not response_message.parts[0].function_call:
            activity.logger.warn("--- 🧠 Agent: Did not select a tool. ---")
            final_summary = response_message.parts[0].text
            if final_summary:
                post_to_slack(final_summary)
            return final_summary

        function_call = response_message.parts[0].function_call
        function_name = function_call.name

        if function_name == "search_logs":
            activity.logger.info(f"--- 🧠 Agent: Decided to call `{function_name}` tool. ---")

            function_args = function_call.args

            # The LLM should no longer invent a path, so this will use the default.
            tool_output = search_logs(
                timestamp_str=function_args.get("timestamp_str"),
                log_file=function_args.get("log_file", "mock_service.log"),
                time_window_seconds=function_args.get("time_window_seconds", 60)
            )

            tool_output_json = json.dumps(tool_output)

            activity.logger.info("--- 🧠 Agent: Sending tool output back to LLM... ---")

            # --- FIX: Use 'genai.types.FunctionResponse' directly ---
            final_response = await chat.send_message_async(
                [
                    genai.types.FunctionResponse(
                        name="search_logs",
                        response={"result": tool_output_json}
                    )
                ]
            )

            final_summary = final_response.candidates[0].content.parts[0].text
            activity.logger.info("--- ✅ Investigation Complete. Final Summary: ---")
            activity.logger.info(final_summary)

            if final_summary:
                post_to_slack(final_summary)

            return final_summary

        else:
            activity.logger.error(f"--- ❌ Agent: Tried to call unknown tool: {function_name} ---")
            return f"Error: Agent tried to call unknown tool {function_name}"

    except Exception as e:
        activity.logger.error(f"--- ❌ FATAL ERROR in investigation: {e} ---")
        # This ensures Temporal knows the activity failed
        raise e