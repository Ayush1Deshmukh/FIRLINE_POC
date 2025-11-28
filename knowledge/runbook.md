# AuthService Runbook

## High CPU Utilization
**Symptoms:** Alerts indicating CPU > 90%.
**Common Causes:**
1. Infinite loop in the token validation logic.
2. Memory leak causing garbage collection thrashing.
3. Stuck database connections.

**Remediation:**
If logs show `NullPointerException` at `com.example.AuthService`, it is a known bug in version 1.2.0.
**Action:** Restart the pod to clear the bad state.
Command: `kubectl rollout restart deployment auth-service`

## Database Connection Failures
**Symptoms:** 500 errors on login.
**Action:** Check the connection pool settings. If max connections are reached, increase the limit in `application.yaml`.
