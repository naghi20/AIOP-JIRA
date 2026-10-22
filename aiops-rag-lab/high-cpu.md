# Runbook: High CPU Utilization on Application Server

## Symptoms
- CPU utilization above 90% for more than 5 minutes
- Application response time increases
- Possible service timeouts

## Likely Causes
- Runaway process consuming CPU
- Insufficient instance size for current load
- Memory pressure causing swap thrashing
- Background job or cron task running longer than expected

## Diagnostic Steps
1. Check top CPU-consuming processes:
   ```bash
   top -b -n 1 | head -20
   ```
2. Check for memory pressure:
   ```bash
   free -m
   ```
3. Check disk I/O wait:
   ```bash
   iostat -x 1 3
   ```
4. Identify the process:
   ```bash
   ps aux --sort=-%cpu | head -10
   ```

## Remediation
- If a known service is stuck, restart it:
  ```bash
  sudo systemctl restart <service-name>
  ```
- If disk cache is causing pressure, clear it:
  ```bash
  sudo sync && sudo sysctl -w vm.drop_caches=3
  ```
- If load is sustained, consider scaling the instance size.

## Escalation
If CPU remains above 90% after remediation, escalate to on-call engineer.
