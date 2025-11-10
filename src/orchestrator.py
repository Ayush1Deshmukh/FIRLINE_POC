import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Import our local tools
from src.tools import search_logs
from src.notifications import post_to_slack

# --- 1. SETUP ---
# Load environment variables from .env file
load_dotenv()

# --- NEW: Setup Google GenAI Client ---
try:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not found. Did you set it in the .env file?")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Error initializing Google GenAI client: {e}")
    # In a real app, we'd use logging, not print

# --- 2. DEFINE THE "TOOLS" FOR THE LLM ---
# This is the JSON Schema for our function, which Google's API understands.
search_logs_tool = {
    "name": "search_logs",
    "description": "Searches a log file for ERROR lines within a time window around a specific timestamp.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "timestamp_str": {
                "type": "STRING",
                "description": "The ISO 8601 timestamp string for the center of the search window (e.g., '2025-10-21T03:05:00Z')."
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
# We configure the model with the system prompt and tools
# We'll use Gemini 1.5 Pro, as it's great at function calling
model = genai.GenerativeModel(
    model_name='gemini-pro',
    system_instruction=SYSTEM_PROMPT,
    tools=[search_logs_tool]  # Pass the tool definition here
)


# --- 5. THE MAIN ORCHESTRATION FUNCTION (REFACTORED) ---
def handle_incident(alert: dict):
    """
    This is the main investigation logic, now using Google Gemini.
    """
    print("--- 🔥 Fireline Investigation Started ---")
    print(f"--- 📥 Received Alert: {alert['error_message']} for {alert['service']} ---")

    # --- Create a new chat session for this incident ---
    chat = model.start_chat()

    # --- First LLM Call: Get the tool to use ---
    print("--- 🧠 Agent: Analyzing alert and selecting tool... ---")
    
    # Send the first message
    user_prompt = f"New Incident Alert: {json.dumps(alert)}"
    response = chat.send_message(user_prompt)
    
    response_message = response.candidates[0].content
    
    # --- 2. Check if the LLM wants to use a tool ---
    if not response_message.parts[0].function_call:
        print("--- 🧠 Agent: Did not select a tool. Providing analysis instead: ---")
        final_summary = response_message.parts[0].text
        print(final_summary)
        if final_summary:
            post_to_slack(final_summary)
        return

    # The model wants to call our tool.
    function_call = response_message.parts[0].function_call
    function_name = function_call.name

    if function_name == "search_logs":
        print(f"--- 🧠 Agent: Decided to call `{function_name}` tool. ---")

        # Get the arguments from the function call
        function_args = function_call.args

        # 3. Call the *actual* Python function
        tool_output = search_logs(
            timestamp_str=function_args.get("timestamp_str"),
            log_file=function_args.get("log_file", "mock_service.log"),
            time_window_seconds=function_args.get("time_window_seconds", 60)
        )
        
        # Convert the list output to a JSON string for the model
        tool_output_json = json.dumps(tool_output)

        print("--- 🧠 Agent: Sending tool output back to LLM for final analysis... ---")

        # 4. Send the tool's results back to the LLM
        # The 'chat' object remembers the history
        final_response = chat.send_message(
            [
                genai.types.Part(
                    function_response=genai.types.FunctionResponse(
                        name="search_logs",
                        response={"result": tool_output_json} # Send tool output as a dict
                    )
                )
            ]
        )

        final_summary = final_response.candidates[0].content.parts[0].text
        print("--- ✅ Investigation Complete. Final Summary: ---")
        print(final_summary)

        # --- 5. POST THE FINAL SUMMARY TO SLACK ---
        if final_summary:
            post_to_slack(final_summary)

    else:
        print(f"--- ❌ Agent: Tried to call an unknown tool: {function_name} ---")
