from typing import Any


class DatabaseTool:
    def save_incident(self, incident: dict[str, Any]) -> dict[str, Any]:
        return {"saved": True, "incident": incident}
