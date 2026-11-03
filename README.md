# Factory Harness

Generic execution harness for software-factory runs.

This repo is intentionally separate from the control plane and from target application repositories. The control plane decides that a job should run; the harness is the executable layer that performs the Git lifecycle inside an isolated environment.

The harness is repo-agnostic. It does not contain `notification-hub` specific instructions, skills, or business logic. The target repository and base branch are supplied through configuration.

## What It Owns

The harness owns the lifecycle from change intent to pull request creation:

```text
job intent
  ↓
read harness config
  ↓
clone target repository
  ↓
create factory job branch
  ↓
make a deterministic placeholder change
  ↓
commit the change
  ↓
push the branch
  ↓
open a pull request
```

Today the code change is only a placeholder file under `.factory-runs/`. That is intentional. It proves the Git and PR mechanics before an agent such as Codex starts making real code changes.

## What It Does Not Own

The harness does not own job intake, queueing, job state, or AWS orchestration. Those belong to the control plane.

The harness also does not launch itself on AWS. In the full system, the worker Lambda in `factory-control-plane` will start a short-lived sandbox, such as an ECS Fargate task, and that sandbox will run this harness container.

## Configuration

The default target is configured in `harness.ini`:

```ini
[target]
repo = abhiverma31/notification-hub
branch = main
```

`repo` is the GitHub repository to clone.

`branch` is the base branch for the run.

## Runner Contract

Required environment variables:

```text
JOB_ID
WORKFLOW_ID
TITLE
DESCRIPTION
```

Optional environment variables:

```text
GITHUB_TOKEN
TARGET_REPO
BASE_BRANCH
CONTROL_PLANE_URL
```

`GITHUB_TOKEN` is required only when the harness should push a branch and open a pull request. Without it, the harness still clones, branches, commits locally, and skips the GitHub write steps.

`TARGET_REPO` overrides `harness.ini`.

`BASE_BRANCH` overrides `harness.ini`.

## Local Run

Local-only run without pushing:

```sh
JOB_ID=local-001 \
WORKFLOW_ID=feature-development \
TITLE="Harness smoke test" \
DESCRIPTION="Confirm clone branch and local commit" \
python3 -m harness.runner
```

Full run with branch push and PR creation:

```sh
GITHUB_TOKEN="..." \
JOB_ID=pr-001 \
WORKFLOW_ID=feature-development \
TITLE="PR smoke test" \
DESCRIPTION="Confirm harness can create a pull request" \
python3 -m harness.runner
```

## Docker

Build:

```sh
docker build -t factory-harness:local .
```

Run without GitHub write access:

```sh
docker run --rm \
  -e JOB_ID=docker-001 \
  -e WORKFLOW_ID=feature-development \
  -e TITLE="Docker harness smoke test" \
  -e DESCRIPTION="Confirm container can create a local commit" \
  factory-harness:local
```

Run with branch push and PR creation:

```sh
docker run --rm \
  -e GITHUB_TOKEN="..." \
  -e JOB_ID=docker-pr-001 \
  -e WORKFLOW_ID=feature-development \
  -e TITLE="Docker PR smoke test" \
  -e DESCRIPTION="Confirm container can create a pull request" \
  factory-harness:local
```
