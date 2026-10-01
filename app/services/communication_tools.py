from __future__ import annotations

from typing import Any

from app.services.provider_router import provider_router


def build_communication_draft(query: str, results: list[dict[str, Any]], mode: str = "mail") -> str:
    if not results:
        return "No matching incident data was available to draft the message."

    top = results[0]
    summary = str(top.get("summary") or "incident")
    root_cause = str(top.get("root_cause") or top.get("resolution") or "root cause not captured").strip()
    resolution = str(top.get("resolution") or "fix details not captured").strip()
    assignee = str(top.get("assignee") or "team member").strip()
    team = str(top.get("team") or "team").strip()

    if mode == "sms":
        return (
            f"Incident update: {summary}. Root cause: {root_cause}. "
            f"Resolution: {resolution}. Assigned to {assignee} in {team}."
        )

    adapter = provider_router.get_llm_adapter()
    if adapter is not None:
        try:
            prompt = (
                "Use only the incident facts below. Keep the email concise and factual. "
                "Do not invent details.\n\n"
                f"Summary: {summary}\n"
                f"Root cause: {root_cause}\n"
                f"Resolution: {resolution}\n"
                f"Assignee: {assignee}\n"
                f"Team: {team}\n\n"
                "Draft a short manager email in professional business style."
            )
            response = adapter.chat(prompt, system_prompt="You are a professional incident communication assistant.")
            content = str(response.get("content") or "").strip()
            if content:
                return content
        except Exception:
            pass

    return (
        "Subject: Incident Update\n\n"
        f"Hi Manager,\n\n"
        f"I wanted to share the latest update on the incident: {summary}. "
        f"The root cause was: {root_cause}. The fix implemented was: {resolution}. "
        f"This issue was handled by {assignee} from the {team} team.\n\n"
        "Regards,\n"
        "Incident Response Team"
    )
