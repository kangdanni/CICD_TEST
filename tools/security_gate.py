# tools/security_gate.py

import json
import os
import sys
import urllib.request
from typing import Any, Dict, List

# 어느 정도 심각도부터 막을지 (bandit)
BANDIT_SEVERITY_THRESHOLD = {"HIGH", "MEDIUM"}
# pip-audit에서 사용할 심각도 기준 (버전에 따라 필드 이름은 조정 필요)
PIP_AUDIT_SEVERITY_THRESHOLD = {"HIGH", "CRITICAL"}


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        print(f"[WARN] Report file not found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to parse JSON from {path}: {e}")
            return None


def analyze_bandit(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not report:
        return []
    results = report.get("results", [])
    severe = [
        r
        for r in results
        if r.get("issue_severity", "").upper() in BANDIT_SEVERITY_THRESHOLD
    ]
    return severe


def analyze_pip_audit(report: Any) -> List[Dict[str, Any]]:
    if not report:
        return []

    severe: List[Dict[str, Any]] = []

    # 최신 pip-audit JSON 포맷 대응
    # - dict 형태: {"dependencies": [ {...}, {...} ]}
    # - 예전/다른 포맷: [ {...}, {...} ] 리턴할 수도 있으니 둘 다 처리
    if isinstance(report, dict):
        items = report.get("dependencies", [])
    elif isinstance(report, list):
        items = report
    else:
        print(f"[WARN] Unexpected pip-audit JSON type: {type(report)}")
        return []

    for item in items:
        # item이 dict인지 방어
        if not isinstance(item, dict):
            continue

        vulns = item.get("vulns", [])
        for v in vulns:
            if not isinstance(v, dict):
                continue

            severity = (v.get("severity") or "").upper()
            if severity in PIP_AUDIT_SEVERITY_THRESHOLD:
                severe.append(
                    {
                        "name": item.get("name"),
                        "version": item.get("version"),
                        "id": v.get("id"),
                        "severity": severity,
                        # pip-audit는 보통 fix_versions (list) 를 씀
                        "fix_versions": v.get("fix_versions"),
                    }
                )

    return severe



def send_slack(text: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        print("[WARN] SLACK_WEBHOOK_URL is not set. Skip Slack notification.")
        return

    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"[INFO] Slack notified. status={resp.status}")
    except Exception as e:
        print(f"[ERROR] Failed to send Slack message: {e}")


def build_slack_message(
    bandit_issues: List[Dict[str, Any]],
    pip_issues: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append(":rotating_light: *Security Gate Alert* :rotating_light:")
    lines.append("")

    if bandit_issues:
        lines.append(f"*Bandit* severe issues: {len(bandit_issues)}")
        for issue in bandit_issues[:10]:
            lines.append(
                f"- [BANDIT] {issue.get('issue_severity')} "
                f"{issue.get('issue_text')} "
                f"(file: {issue.get('filename')}, line: {issue.get('line_number')})"
            )
        if len(bandit_issues) > 10:
            lines.append(f"... and {len(bandit_issues) - 10} more")
        lines.append("")

    if pip_issues:
        lines.append(f"*pip-audit* severe issues: {len(pip_issues)}")
        for issue in pip_issues[:10]:
            lines.append(
                f"- [PIP] {issue['severity']} {issue['name']} "
                f"{issue['version']} (id: {issue['id']}, fix: {issue.get('fix_version')})"
            )
        if len(pip_issues) > 10:
            lines.append(f"... and {len(pip_issues) - 10} more")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: security_gate.py <bandit-report.json> <pip-audit-report.json>")
        sys.exit(1)

    bandit_path = sys.argv[1]
    pip_path = sys.argv[2]

    bandit_report = load_json(bandit_path)
    pip_report = load_json(pip_path)

    severe_bandit = analyze_bandit(bandit_report)
    severe_pip = analyze_pip_audit(pip_report)

    if not severe_bandit and not severe_pip:
        print("[INFO] No severe security issues found. Security gate passed.")
        sys.exit(0)

    msg = build_slack_message(severe_bandit, severe_pip)
    print(msg)

    # 슬랙 알림
    send_slack(msg)

    # 머지 차단(워크플로우 실패)
    print("[ERROR] Severe security issues detected. Failing job.")
    sys.exit(1)


if __name__ == "__main__":
    main()
