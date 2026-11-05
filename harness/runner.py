import configparser
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_ENV = [
    "JOB_ID",
    "WORKFLOW_ID",
    "TITLE",
    "DESCRIPTION",
]
CONFIG_PATH = Path(__file__).resolve().parents[1] / "harness.ini"
WORKSPACE_ROOT = Path("/tmp/factory-harness")


def main():
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    config = load_config()
    target_repo = os.environ.get("TARGET_REPO") or config.get("target", "repo", fallback="")
    base_branch = os.environ.get("BASE_BRANCH") or os.environ.get("TARGET_BRANCH") or config.get("target", "branch", fallback="main")

    if not target_repo:
        raise SystemExit("Missing target repo. Set TARGET_REPO or [target].repo in harness.ini")

    payload = {
        "jobId": os.environ["JOB_ID"],
        "workflowId": os.environ["WORKFLOW_ID"],
        "targetRepo": target_repo,
        "baseBranch": base_branch,
        "title": os.environ["TITLE"],
        "description": os.environ["DESCRIPTION"],
        "controlPlaneUrl": os.environ.get("CONTROL_PLANE_URL", ""),
        "changeMode": os.environ.get("CHANGE_MODE", "placeholder"),
        "startedAt": utc_now(),
    }
    report_event(payload, "HARNESS_STARTED", "Harness started running.")

    try:
        repo_path = clone_target_repo(payload["jobId"], target_repo, base_branch)
        clone = summarize_clone(repo_path)
        change = create_change(repo_path, payload)
        push = push_change(repo_path, change["runBranch"])
        pull_request = create_pull_request(payload, change["runBranch"], push)
        if pull_request["enabled"]:
            report_event(
                payload,
                "PR_CREATED",
                "Harness created a pull request.",
                {
                    "number": pull_request["number"],
                    "url": pull_request["url"],
                },
            )

        result = {
            "message": "Factory harness prepared target repository change",
            "payload": payload,
            "clone": clone,
            "change": change,
            "push": push,
            "pullRequest": pull_request,
        }

        report_event(
            payload,
            "HARNESS_COMPLETED",
            "Harness completed successfully.",
            {
                "clone": clone,
                "change": change,
                "push": push,
                "pullRequest": pull_request,
            },
        )

        print(json.dumps(result))
    except (Exception, SystemExit) as error:
        report_event(
            payload,
            "JOB_FAILED",
            "Harness failed.",
            {
                "error": str(error),
            },
        )
        raise


def clone_target_repo(job_id, target_repo, base_branch):
    workspace = WORKSPACE_ROOT / job_id
    repo_path = workspace / "repo"

    if workspace.exists():
        shutil.rmtree(workspace)

    workspace.mkdir(parents=True, exist_ok=True)
    repo_url = f"https://github.com/{target_repo}.git"

    run(
        [
            "git",
            "clone",
            "--branch",
            base_branch,
            "--single-branch",
            repo_url,
            str(repo_path),
        ]
    )
    return repo_path


def create_change(repo_path, payload):
    if payload["changeMode"] == "placeholder":
        return create_placeholder_change(repo_path, payload)

    if payload["changeMode"] == "codex":
        return create_codex_change(repo_path, payload)

    raise SystemExit(f"Unsupported CHANGE_MODE: {payload['changeMode']}")


def summarize_clone(repo_path):
    top_level_entries = sorted(path.name for path in repo_path.iterdir())
    file_count = sum(1 for path in repo_path.rglob("*") if path.is_file() and ".git" not in path.parts)
    head_sha = run(["git", "-C", str(repo_path), "rev-parse", "HEAD"]).stdout.strip()

    return {
        "repoPath": str(repo_path),
        "headSha": head_sha,
        "fileCount": file_count,
        "topLevelEntries": top_level_entries[:20],
    }


def create_codex_change(repo_path, payload):
    run_branch = f"factory/job-{payload['jobId']}"
    run(["git", "-C", str(repo_path), "checkout", "-b", run_branch])

    prompt = "\n".join(
        [
            "You are running inside an automated software-factory harness.",
            "You must modify repository files to satisfy the job request.",
            "Do not answer with an explanation only.",
            "Do not commit, push, or open a pull request.",
            "After editing, leave changes unstaged for the harness to commit.",
            "Keep changes focused and avoid unrelated refactors.",
            "If tests need updating, update the narrowest relevant tests only.",
            "",
            f"Workflow: {payload['workflowId']}",
            f"Title: {payload['title']}",
            f"Description: {payload['description']}",
        ]
    )

    run_codex(repo_path, prompt)

    status = run(["git", "-C", str(repo_path), "status", "--short"]).stdout.strip()
    if not status:
        raise SystemExit("Codex completed without creating any git changes")

    run(["git", "-C", str(repo_path), "config", "user.name", "Factory Harness"])
    run(["git", "-C", str(repo_path), "config", "user.email", "factory-harness@example.invalid"])
    run(["git", "-C", str(repo_path), "add", "."])
    run(["git", "-C", str(repo_path), "commit", "-m", f"Apply factory change for {payload['jobId']}"])

    commit_sha = run(["git", "-C", str(repo_path), "rev-parse", "HEAD"]).stdout.strip()
    committed_status = run(["git", "-C", str(repo_path), "status", "--short"]).stdout.strip()

    return {
        "mode": "codex",
        "runBranch": run_branch,
        "commitSha": commit_sha,
        "status": committed_status,
    }


def run_codex(repo_path, prompt):
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("Codex CLI was not found in the harness image")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for CHANGE_MODE=codex")

    codex_env = {
        **os.environ,
        "OPENAI_API_KEY": api_key,
        "CODEX_API_KEY": api_key,
    }

    run(
        [
            codex,
            "exec",
            "--skip-git-repo-check",
            "--approve-for-me",
            prompt,
        ],
        cwd=repo_path,
        env=codex_env,
        timeout=int(os.environ.get("CODEX_TIMEOUT_SECONDS", "300")),
    )


def create_placeholder_change(repo_path, payload):
    run_branch = f"factory/job-{payload['jobId']}"
    run(["git", "-C", str(repo_path), "checkout", "-b", run_branch])

    run_dir = repo_path / ".factory-runs"
    run_dir.mkdir(exist_ok=True)
    run_file = run_dir / f"{payload['jobId']}.md"
    run_file.write_text(render_placeholder_run(payload, run_branch), encoding="utf-8")

    run(["git", "-C", str(repo_path), "config", "user.name", "Factory Harness"])
    run(["git", "-C", str(repo_path), "config", "user.email", "factory-harness@example.invalid"])
    run(["git", "-C", str(repo_path), "add", str(run_file.relative_to(repo_path))])
    run(["git", "-C", str(repo_path), "commit", "-m", f"Record factory run {payload['jobId']}"])

    status = run(["git", "-C", str(repo_path), "status", "--short"]).stdout.strip()
    commit_sha = run(["git", "-C", str(repo_path), "rev-parse", "HEAD"]).stdout.strip()

    return {
        "runBranch": run_branch,
        "placeholderFile": str(run_file.relative_to(repo_path)),
        "commitSha": commit_sha,
        "status": status,
    }


def push_change(repo_path, run_branch):
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        return {
            "enabled": False,
            "reason": "GITHUB_TOKEN not set",
        }

    origin_url = run(["git", "-C", str(repo_path), "remote", "get-url", "origin"]).stdout.strip()
    push_url = origin_url.replace("https://github.com/", f"https://x-access-token:{github_token}@github.com/")

    run(["git", "-C", str(repo_path), "push", push_url, run_branch])

    return {
        "enabled": True,
        "branch": run_branch,
    }


def create_pull_request(payload, run_branch, push):
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token or not push["enabled"]:
        return {
            "enabled": False,
            "reason": "GITHUB_TOKEN not set or branch was not pushed",
        }

    title = f"[Factory] {payload['title']}"
    body = "\n".join(
        [
            f"Factory job: {payload['jobId']}",
            f"Workflow: {payload['workflowId']}",
            "",
            payload["description"],
        ]
    )
    request_body = json.dumps(
        {
            "title": title,
            "head": run_branch,
            "base": payload["baseBranch"],
            "body": body,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.github.com/repos/{payload['targetRepo']}/pulls",
        data=request_body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "Content-Type": "application/json",
            "User-Agent": "factory-harness",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(
            json.dumps(
                {
                    "message": "GitHub pull request creation failed",
                    "status": error.code,
                    "body": error.read().decode("utf-8"),
                }
            )
        )

    return {
        "enabled": True,
        "number": response_body["number"],
        "url": response_body["html_url"],
    }


def report_event(payload, event_type, message, details=None):
    control_plane_url = payload.get("controlPlaneUrl")
    if not control_plane_url:
        return {
            "enabled": False,
            "reason": "CONTROL_PLANE_URL not set",
        }

    request_body = json.dumps(
        {
            "type": event_type,
            "message": message,
            "details": details or {},
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{control_plane_url.rstrip('/')}/jobs/{payload['jobId']}/events",
        data=request_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "factory-harness",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise SystemExit(
            json.dumps(
                {
                    "message": "Control-plane event reporting failed",
                    "eventType": event_type,
                    "status": error.code,
                    "body": error.read().decode("utf-8"),
                }
            )
        )
    except urllib.error.URLError as error:
        raise SystemExit(
            json.dumps(
                {
                    "message": "Control-plane event reporting failed",
                    "eventType": event_type,
                    "reason": str(error.reason),
                }
            )
        )

    return {
        "enabled": True,
        "eventType": event_type,
        "response": json.loads(response_body) if response_body else {},
    }


def render_placeholder_run(payload, run_branch):
    return f"""# Factory Run {payload["jobId"]}

- Workflow: {payload["workflowId"]}
- Target repo: {payload["targetRepo"]}
- Base branch: {payload["baseBranch"]}
- Run branch: {run_branch}
- Title: {payload["title"]}
- Description: {payload["description"]}
- Started at: {payload["startedAt"]}
"""


def run(command, cwd=None, input_text=None, env=None, timeout=None):
    result = subprocess.run(command, text=True, capture_output=True, cwd=cwd, input=input_text, env=env, timeout=timeout)
    if result.returncode != 0:
        raise SystemExit(
            json.dumps(
                {
                    "message": "Command failed",
                    "command": command,
                    "returnCode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
        )
    return result


def load_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    main()
