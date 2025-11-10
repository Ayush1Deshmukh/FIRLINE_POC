from temporalio import workflow
import dataclasses
from datetime import timedelta

# Import the activity function we just defined
# Note: We import from src.activities, NOT src.orchestrator
from src.activities import run_investigation

# A workflow is defined as a class
@workflow.defn
class IncidentWorkflow:

    # The @workflow.run method is the entrypoint
    @workflow.run
    async def run(self, alert: dict) -> str:
        """
        This workflow orchestrates the entire incident investigation.
        """
        workflow.logger.info(f"--- 🏁 Workflow started for {alert['service']} ---")

        # This is how you execute an activity.
        # Temporal will find a Worker and tell it to run
        # the 'run_investigation' function with our 'alert' object.
        summary = await workflow.execute_activity(
            run_investigation,
            alert,
            start_to_close_timeout=timedelta(minutes=5),
            # This ensures the activity is retried if it fails
            retry_policy=workflow.RetryPolicy(
                maximum_attempts=3
            )
        )

        workflow.logger.info("--- 🏁 Workflow finished. ---")
        return summary