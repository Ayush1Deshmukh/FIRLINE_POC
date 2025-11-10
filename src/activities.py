import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from temporalio import activity  # <-- 1. IMPORT TEMPORAL'S ACTIVITY DECORATOR

# Import our local tools
from src.tools import search_logs
from src.notifications import post_to_slack

# --- 1. SETUP ---
load_dotenv()

# --- NEW: Setup Google GenAI Client ---
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found. Did you set it in the .env file?")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    activity.logger.error(f"Error initializing Google GenAI client: {e}")
    # We'll let the activity fail if the client can't be set up.

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
                "description": "The path to the log file to search."
            },
            "time_window_seconds": {
                "type": "INTEGER",
                "description": "The total number of seconds for the search window (e.g., 60 means 30s before and 30s after the timestamp)."
            }
        },
        "required": ["timestamp_str", "log_file"]
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
4. Once you receive the tool's output (e.g., log lines), analyze them.
5. Provide a concise, final summary of your findings and a root cause hypothesis.
6. Do NOT make up information. Base your summary *only* on the tool's output.
"""

# --- 4. CREATE THE MODEL ---
# This is fine to define globally. The model client is thread-safe.
model = genai.GenerativeModel(
    model_name='gemini-pro',
    system_instruction=SYSTEM_PROMPT,
    tools=[search_logs_tool]
)


# --- 5. THE ACTIVITY DEFINITION ---
@activity.defn  # <-- 2. ADD THE DECORATOR
async def run_investigation(alert: dict) -> str:  # <-- 3. MAKE IT 'async'
    """
    This is the main investigation Activity, using Google Gemini.
    """
    # 4. USE THE ACTIVITY LOGGER, NOT print()
    activity.logger.info(f"--- 🔥 Fireline Investigation Started for {alert['service']} ---")

    # --- Create a new chat session for this incident ---
    chat = model.start_chat()

    # --- First LLM Call: Get the tool to use ---
    activity.logger.info("--- 🧠 Agent: Analyzing alert and selecting tool... ---")
    
    user_prompt = f"New Incident Alert: {json.dumps(alert)}"
    
    # 5. USE THE ASYNC 'await' SYNTAX
    response = await chat.send_message_async(user_prompt)
    
    response_message = response.candidates[0].content
    
    # --- 2. Check if the LLM wants to use a tool ---
    if not response_message.parts[0].function_call:
        activity.logger.warn("--- 🧠 Agent: Did not select a tool. Providing analysis instead: ---")
        final_summary = response_message.parts[0].text
        activity.logger.info(final_summary)
        if final_summary:
            post_to_slack(final_summary)
        return final_summary  # <-- 6. RETURN A VALUE

    # The model wants to call our tool.
    function_call = response_message.parts[0].function_call
    function_name = function_call.name

    if function_name == "search_logs":
        activity.logger.info(f"--- 🧠 Agent: Decided to call `{function_name}` tool. ---")

        function_args = function_call.args

        # 3. Call the *actual* Python function (this is sync, which is fine)
        tool_output = search_logs(
            timestamp_str=function_args.get("timestamp_str"),
            log_file=function_args.get("log_file", "mock_service.log"),
            time_window_seconds=function_args.get("time_window_seconds", 60)
        )
        
        tool_output_json = json.dumps(tool_output)

        activity.logger.info("--- 🧠 Agent: Sending tool output back to LLM for final analysis... ---")

        # 4. Send the tool's results back to the LLM (using async)
        final_response = await chat.send_message_async(
            [
                genai.types.Part(
                    function_response=genai.types.FunctionResponse(
                        name="search_logs",
                        response={"result": tool_output_json}
                    )
                )
            ]
        )

        final_summary = final_response.candidates[0].content.parts[0].text
        activity.logger.info("--- ✅ Investigation Complete. Final Summary: ---")
        activity.logger.info(final_summary)

        # --- 5. POST THE FINAL SUMMARY TO SLACK ---
        if final_summary:
            post_to_slack(final_summary)

        return final_summary  # <-- 6. RETURN THE FINAL RESULT

    else:
        activity.logger.error(f"--- ❌ Agent: Tried to call an unknown tool: {function_name} ---")
        return f"Error: Agent tried to call unknown tool {function_name}"