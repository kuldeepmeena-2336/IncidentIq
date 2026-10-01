from __future__ import annotations

from typing import Any


class JiraTool:
    def _extract_comments(self, fields: dict[str, Any]) -> list[str]:
        comment_block = fields.get("comment") or fields.get("comments") or {}
        if isinstance(comment_block, dict):
            comments = comment_block.get("comments", [])
        elif isinstance(comment_block, list):
            comments = comment_block
        else:
            comments = []

        extracted: list[str] = []
        for item in comments:
            if isinstance(item, dict):
                body = item.get("body") or item.get("text")
                if body:
                    extracted.append(str(body))
            elif isinstance(item, str):
                extracted.append(item)
        return extracted

    def _extract_label(self, fields: dict[str, Any], issue: dict[str, Any]) -> str | None:
        label = fields.get("label") or issue.get("label")
        if label:
            return str(label)
        labels = fields.get("labels") or issue.get("labels") or []
        if isinstance(labels, list) and labels:
            return str(labels[0])
        return None

    def _extract_root_cause(self, comments: list[str]) -> str | None:
        for body in comments:
            lowered = body.lower()
            if "root cause" in lowered or "rca" in lowered or "cause" in lowered:
                return body
        return None

    def _extract_resolution(self, comments: list[str]) -> str | None:
        for body in comments:
            lowered = body.lower()
            if any(keyword in lowered for keyword in ["fix:", "fixed", "resolution", "mitigated", "re-enabled", "implemented", "resolved", "updated trust store", "increased worker count"]):
                return body
        return None

    def parse_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "issue_key": None,
                "summary": None,
                "description": None,
                "status": None,
                "priority": None,
                "assignee": None,
                "reporter": None,
                "label": None,
                "comments": [],
                "root_cause": None,
                "resolution": None,
                "raw_payload": payload,
            }

        issue = payload.get("issue", payload)
        fields = issue.get("fields", issue) if isinstance(issue, dict) else {}
        issue_key = (
            issue.get("key")
            or issue.get("issueKey")
            or payload.get("issueKey")
            or payload.get("issue_key")
            or payload.get("key")
        )

        description = fields.get("description")
        if isinstance(description, dict):
            description = description.get("content")
        if isinstance(description, list):
            description = "\n".join(
                part.get("content", [{}])[0].get("text", "")
                if isinstance(part, dict) and isinstance(part.get("content", []), list)
                else ""
                for part in description
            )
        if description is None:
            description = issue.get("description") or payload.get("description")

        summary = fields.get("summary") or issue.get("summary") or payload.get("summary")
        status = fields.get("status", {}).get("name") if isinstance(fields.get("status"), dict) else fields.get("status") or payload.get("status")
        priority = fields.get("priority", {}).get("name") if isinstance(fields.get("priority"), dict) else fields.get("priority") or payload.get("priority")
        issue_type = fields.get("issuetype", {}).get("name") if isinstance(fields.get("issuetype"), dict) else fields.get("issuetype")
        project = fields.get("project", {}).get("key") if isinstance(fields.get("project"), dict) else fields.get("project")
        components = fields.get("components", [])
        labels = fields.get("labels", [])
        assignee = fields.get("assignee", {}).get("name") if isinstance(fields.get("assignee"), dict) else fields.get("assignee") or payload.get("assignee")
        reporter = fields.get("reporter", {}).get("name") if isinstance(fields.get("reporter"), dict) else fields.get("reporter") or payload.get("reporter")
        comment_list = self._extract_comments(fields)
        root_cause = self._extract_root_cause(comment_list)
        resolution = self._extract_resolution(comment_list)
        label = self._extract_label(fields, issue)

        return {
            "issue_key": issue_key,
            "summary": summary,
            "description": description,
            "status": status,
            "priority": priority,
            "issue_type": issue_type,
            "project": project,
            "components": [component.get("name") for component in components if isinstance(component, dict)] if isinstance(components, list) else components,
            "labels": labels,
            "assignee": assignee,
            "reporter": reporter,
            "label": label,
            "comments": comment_list,
            "root_cause": root_cause,
            "resolution": resolution,
            "raw_payload": payload,
        }
