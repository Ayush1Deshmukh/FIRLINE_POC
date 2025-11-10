from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, Field

# Import our refactored investigation logic
from src.orchestrator import handle_incident

# 1. Create the FastAPI "app" instance
app = FastAPI(
    title="Fireline API",
    description="API for the Fireline SRE Incident Commander"
)

# 2. Define the *expected* data shape for an alert
# This is a Pydantic model. It provides automatic data validation.
class Alert(BaseModel):
    timestamp: str = Field(..., example="2025-10-21T03:05:00Z")
    service: str = Field(..., example="auth-service")
    error_message: str = Field(..., example="High CPU Utilization")


# 3. Create a "GET" endpoint for basic health checks
@app.get("/")
def read_root():
    """A simple endpoint to check if the API is online."""
    return {"status": "Fireline API is running"}


# 4. Create the "POST" endpoint for receiving webhooks
@app.post("/webhook/alert")
def post_new_alert(alert: Alert, background_tasks: BackgroundTasks):
    """
    This is the main webhook endpoint.
    It receives an alert, validates it using the Alert model,
    and hands off the investigation to a background task.
    """

    print(f"--- 🚀 API: New alert received for {alert.service} ---")

    # SDE Best Practice: Don't make the user wait!
    # An HTTP request should return in <1 second.
    # Our investigation takes 10-20 seconds.
    # So, we add the *long* task to the background.
    background_tasks.add_task(handle_incident, alert.model_dump())

    # And return an "OK" message *immediately*.
    return {"status": "investigation_started"}
