import uuid
from fastapi import FastAPI
from pydantic import BaseModel, Field
from temporalio.client import Client
# We import IncidentWorkflow just to get the signal name, but we start by string
from src.workflows import IncidentWorkflow

# --- TEMPORAL CLIENT SETUP ---
temporal_client = None

# --- IN-MEMORY DATABASE (For POC UI) ---
# In production, this would be a Postgres table.
active_incidents = {} 

app = FastAPI(
    title="Fireline API",
    description="API for the Fireline SRE Incident Commander"
)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows Streamlit Cloud to connect
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
async def startup_event():
    """On API startup, connect to the Temporal server."""
    global temporal_client
    temporal_client = await Client.connect("127.0.0.1:7233")
    print("--- 🚀 API: Connected to Temporal server ---")


class Alert(BaseModel):
    timestamp: str = Field(..., example="2025-10-21T03:05:00Z")
    service: str = Field(..., example="auth-service")
    error_message: str = Field(..., example="High CPU Utilization")

@app.get("/")
def read_root():
    return {"status": "Fireline API is running"}

# --- NEW: Endpoint for UI to fetch incidents ---
@app.get("/incidents")
def get_incidents():
    return list(active_incidents.values())

@app.post("/webhook/alert")
async def post_new_alert(alert: Alert):
    print(f"--- 🚀 API: New alert received for {alert.service} ---")

    # Create a unique ID for this specific run
    workflow_id = f"incident-{uuid.uuid4()}"

    # Store in our "mock DB" so the UI can see it
    active_incidents[workflow_id] = {
        "id": workflow_id,
        "service": alert.service,
        "error": alert.error_message,
        "status": "investigating", # investigating, approved
        "timestamp": alert.timestamp
    }

    # Start the workflow
    await temporal_client.start_workflow(
        "IncidentWorkflow", # Use string name
        alert.model_dump(),
        id=workflow_id,
        task_queue="fireline-task-queue",
    )

    return {"status": "investigation_workflow_started", "id": workflow_id}

@app.post("/incident/{workflow_id}/approve")
async def approve_incident(workflow_id: str):
    """
    Sends an approval signal to a running workflow.
    """
    print(f"--- 👮‍♂️ API: Approving workflow {workflow_id} ---")

    # Get the handle to the running workflow
    handle = temporal_client.get_workflow_handle(workflow_id)

    # Send the signal. We use the method name from the class as the signal name.
    await handle.signal(IncidentWorkflow.approve_action)

    # Update our mock DB
    if workflow_id in active_incidents:
        active_incidents[workflow_id]["status"] = "approved"

    return {"status": "approved", "workflow_id": workflow_id}
@app.get("/incident/{workflow_id}/analysis")
async def get_incident_analysis(workflow_id: str):
    """
    Queries the running workflow to get the AI's investigation summary.
    """
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        # Query the workflow for the 'get_current_summary' method
        summary = await handle.query(IncidentWorkflow.get_current_summary)
        return {"analysis": summary}
    except Exception as e:
        return {"analysis": "Waiting for investigation..."}
