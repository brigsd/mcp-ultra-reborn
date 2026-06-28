"""Gerenciamento de planos de execução persistentes.

Os planos são armazenados como arquivos JSON em `.qwen-plans/` dentro do
diretório de trabalho da sessão. Cada plano tem um ID único, título, lista
de passos e timestamps.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal


StepStatus = Literal["pending", "in_progress", "done"]


@dataclass
class Step:
    description: str
    status: StepStatus = "pending"

    def to_dict(self) -> dict:
        return {"description": self.description, "status": self.status}

    @classmethod
    def from_dict(cls, d: dict) -> Step:
        return cls(description=d["description"], status=d.get("status", "pending"))


@dataclass
class Plan:
    id: str
    title: str
    steps: list[Step] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Plan:
        return cls(
            id=d["id"],
            title=d["title"],
            steps=[Step.from_dict(s) for s in d.get("steps", [])],
            created_at=d.get("created_at", 0),
            updated_at=d.get("updated_at", 0),
        )

    def render(self) -> str:
        """Renderiza o plano como texto legível."""
        status_icons = {"pending": "[ ]", "in_progress": "[/]", "done": "[x]"}
        lines = [f"# Plano: {self.title}  (id: {self.id})"]
        for i, step in enumerate(self.steps, 1):
            icon = status_icons.get(step.status, "[ ]")
            lines.append(f"  {i}. {icon} {step.description}")
        done = sum(1 for s in self.steps if s.status == "done")
        total = len(self.steps)
        lines.append(f"\nProgresso: {done}/{total} concluído(s)")
        return "\n".join(lines)


class PlanManager:
    """CRUD de planos persistidos em disco."""

    def __init__(self, base_dir: str):
        self._dir = os.path.join(base_dir, ".qwen-plans")

    def _ensure_dir(self) -> None:
        os.makedirs(self._dir, exist_ok=True)

    def _plan_path(self, plan_id: str) -> str:
        # Sanitiza o ID para evitar path traversal
        safe = plan_id.replace("/", "").replace("\\", "").replace("..", "")
        return os.path.join(self._dir, f"{safe}.json")

    def create(self, title: str, step_descriptions: list[str]) -> Plan:
        self._ensure_dir()
        plan = Plan(
            id=uuid.uuid4().hex[:8],
            title=title,
            steps=[Step(description=d) for d in step_descriptions],
        )
        self._save(plan)
        return plan

    def get(self, plan_id: str) -> Plan | None:
        path = self._plan_path(plan_id)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return Plan.from_dict(json.load(f))

    def update_step(self, plan_id: str, step_index: int, status: StepStatus) -> Plan | None:
        plan = self.get(plan_id)
        if plan is None:
            return None
        if step_index < 1 or step_index > len(plan.steps):
            return None
        plan.steps[step_index - 1].status = status
        plan.updated_at = time.time()
        self._save(plan)
        return plan

    def list_plans(self) -> list[Plan]:
        self._ensure_dir()
        plans = []
        for name in sorted(os.listdir(self._dir)):
            if name.endswith(".json"):
                path = os.path.join(self._dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        plans.append(Plan.from_dict(json.load(f)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return plans

    def _save(self, plan: Plan) -> None:
        path = self._plan_path(plan.id)
        with open(path, "w", encoding="utf-8", newline="") as f:
            json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
