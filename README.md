# Factory Harness

Generic execution harness for software-factory runs.

This repo is intentionally separate from the control plane and from target application repositories. The harness is responsible for running a job in an isolated environment and reporting progress/results back to the control plane.

## Current Goal

The first slice is deliberately small:

```text
read job input from environment variables
normalize it into a run payload
print the payload as JSON
exit successfully
```

No repository checkout, Codex invocation, branch push, or PR creation yet.

## Runner Contract

The runner currently reads:

```text
JOB_ID
WORKFLOW_ID
TARGET_REPO
BASE_BRANCH
TITLE
DESCRIPTION
CONTROL_PLANE_URL
```

Example:

```sh
JOB_ID=job-123 \
WORKFLOW_ID=feature-development \
TARGET_REPO=abhiverma31/notification-hub \
BASE_BRANCH=main \
TITLE="Add registration validation" \
DESCRIPTION="Validate phone number during customer registration" \
CONTROL_PLANE_URL="https://example.lambda-url.us-east-1.on.aws" \
python -m harness.runner
```

## Docker

Build:

```sh
docker build -t factory-harness:local .
```

Run:

```sh
docker run --rm \
  -e JOB_ID=job-123 \
  -e WORKFLOW_ID=feature-development \
  -e TARGET_REPO=abhiverma31/notification-hub \
  -e BASE_BRANCH=main \
  -e TITLE="Add registration validation" \
  -e DESCRIPTION="Validate phone number during customer registration" \
  -e CONTROL_PLANE_URL="https://example.lambda-url.us-east-1.on.aws" \
  factory-harness:local
```
