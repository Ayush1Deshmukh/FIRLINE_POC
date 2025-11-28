import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from temporalio import activity
import asyncio

# Import our local tools
from src.tools import search_logs, search_runbooks
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

# --- 2. DEFINE THE TOOLS ---
search_logs_tool = {
    "name": "search_logs",
    "description": "Searches a log file for ERROR lines within a time window around a specific timestamp.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "timestamp_str": { "type": "STRING", "description": "The ISO 8601 timestamp string." },
            # We hide the log_file parameter so the AI stops guessing it
            "time_window_seconds": { "type": "INTEGER", "description": "The total number of seconds for the search window." }
        },
        "required": ["timestamp_str"] 
    }
}

search_runbooks_tool = {
    "name": "search_runbooks",
    "description": "Searches the runbook database for known fixes and remediation steps.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query_text": { "type": "STRING", "description": "The error message or symptom to search for (e.g. 'High CPU', 'NullPointerException')." }
        },
        "required": ["query_text"]
    }
}

# --- 3. DEFINE THE AGENT'S TASK ---
SYSTEM_PROMPT = """
You are "Fireline-01", an expert SRE Incident Commander.
Your goal is to:
1. IDENTIFY the root cause using logs.
2. FIND the remediation using the runbook.
3. REPORT the specific commands to fix it.

Process:
- Start by searching logs around the alert time.
- Analyze the log errors.
- IF you find a specific error, call the `search_runbooks` tool to find a fix.
- Once you have the fix, provide a final summary.
"""

# --- 4. CREATE THE MODEL ---
model = genai.GenerativeModel(
    model_name='models/gemini-pro-latest',
    system_instruction=SYSTEM_PROMPT,
    tools=[search_logs_tool, search_runbooks_tool]
)


# --- 5. THE ACTIVITY DEFINITIONS ---

@activity.defn
async def execute_remediation(command: str) -> str:
    """
    Executes the remediation command.
    """
    activity.logger.info(f"--- ⚠️ EXECUTING REMEDIATION: {command} ---")

    # Simulate a delay
    await asyncio.sleep(2)

    result = f"Successfully executed: {command}. Service health checks passing."
    activity.logger.info(f"--- ✅ Execution Complete: {result} ---")

    return result

@activity.defn
async def run_investigation(alert: dict) -> str:
    activity.logger.info(f"--- 🔥 Fireline Investigation Started for {alert['service']} ---")

    chat = model.start_chat()
    user_prompt = f"New Incident Alert: {json.dumps(alert)}"

    # --- THE AGENT LOOP (Max 5 Turns) ---
    for turn in range(5):
        activity.logger.info(f"--- 🔄 Turn {turn + 1}: Asking LLM... ---")

        try:
            # Send message (user prompt on first turn, empty on subsequent turns)
            response = await chat.send_message_async(user_prompt if turn == 0 else [])
            response_message = response.candidates[0].content

            # CHECK: Does the AI want to use a tool?
            if not response_message.parts[0].function_call:
                activity.logger.info("--- 🧠 Agent decided to stop. Finalizing... ---")
                final_summary = response_message.parts[0].text

                if final_summary:
                    post_to_slack(final_summary)
                return final_summary

            # EXECUTE: The AI wants to use a tool
            function_call = response_message.parts[0].function_call
            function_name = function_call.name
            function_args = function_call.args

            activity.logger.info(f"--- 🛠️ Calling Tool: {function_name} ---")
            tool_result_json = "{}"

            if function_name == "search_logs":
                # FIX 1: We FORCE the mock file. We do not trust the AI to guess the path.
                tool_output = search_logs(
                    timestamp_str=function_args.get("timestamp_str"),
                    log_file="mock_service.log", 
                    time_window_seconds=function_args.get("time_window_seconds", 60)
                )
                tool_result_json = json.dumps(tool_output)

            elif function_name == "search_runbooks":
                query_text = function_args.get("query_text")
                tool_output = search_runbooks(query_text)
                tool_result_json = json.dumps(tool_output)

            else:
                activity.logger.error(f"Unknown tool: {function_name}")
                tool_result_json = json.dumps({"error": "Unknown tool"})

            # RESPOND: Send tool output back to the AI
            # FIX 2: We use a raw DICTIONARY to avoid import errors
            response_part = {
                "function_response": {
                    "name": function_name,
                    "response": {"result": tool_result_json}
                }
            }

            await chat.send_message_async(response_part)

        except Exception as e:
            activity.logger.error(f"--- ❌ FATAL ERROR in investigation: {e} ---")
            raise e

    return "Agent reached max turns without resolution."