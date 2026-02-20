"""
Scope of Work Templates API
Provides industry-specific scope of work templates for the scope builder
"""

import json
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/scope-templates", tags=["scope-templates"])


class Task(BaseModel):
    id: str
    label: str
    description: Optional[str] = None


class ServiceArea(BaseModel):
    id: str
    name: str
    icon: str
    tasks: List[Task]


class ScopeTemplate(BaseModel):
    name: str
    service_areas: List[ServiceArea]


class TemplateListResponse(BaseModel):
    templates: List[str]


class TemplateResponse(BaseModel):
    template: ScopeTemplate


def load_templates():
    """Load scope of work templates from JSON file"""
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "cleanenroll_scope_of_work_templates.json"
    )

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("templates", [])


def normalize_template_name(name: str) -> str:
    """Normalize template name for comparison (lowercase, no spaces)"""
    return name.lower().replace(" ", "").replace("-", "")


def generate_task_id(task_label: str) -> str:
    """Generate a task ID from the task label"""
    return task_label.lower().replace(" ", "-").replace("/", "-").replace("(", "").replace(")", "")


def generate_area_id(area_name: str) -> str:
    """Generate an area ID from the area name"""
    return area_name.lower().replace(" ", "-").replace("/", "-")


def get_area_icon(area_name: str) -> str:
    """Get an appropriate icon for a service area"""
    area_lower = area_name.lower()

    icon_map = {
        "lobby": "🏢",
        "reception": "🏢",
        "workstation": "💼",
        "office": "💼",
        "conference": "📊",
        "meeting": "📊",
        "breakroom": "☕",
        "kitchenette": "☕",
        "kitchen": "🍳",
        "restroom": "🚻",
        "bathroom": "🚻",
        "sales": "🛍️",
        "retail": "🛍️",
        "fitting": "👔",
        "checkout": "💳",
        "pos": "💳",
        "stockroom": "📦",
        "storage": "📦",
        "warehouse": "📦",
        "dining": "🍽️",
        "cafeteria": "🍽️",
        "bar": "🍸",
        "grease": "🧴",
        "exam": "🏥",
        "medical": "🏥",
        "waiting": "🪑",
        "clinical": "🧪",
        "biohazard": "⚠️",
        "production": "🏭",
        "industrial": "🏭",
        "loading": "🚚",
        "dock": "🚚",
        "workout": "🏋️",
        "gym": "🏋️",
        "locker": "🚿",
        "classroom": "📚",
        "hallway": "🚶",
        "common": "🚶",
    }

    for key, icon in icon_map.items():
        if key in area_lower:
            return icon

    return "📋"


@router.get("/list", response_model=TemplateListResponse)
async def list_templates():
    """Get list of available template names"""
    try:
        templates = load_templates()
        template_names = [t["name"] for t in templates]
        return TemplateListResponse(templates=template_names)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load templates: {str(e)}")


@router.get("/{template_name}", response_model=TemplateResponse)
async def get_template(template_name: str):
    """
    Get scope of work template by name

    Args:
        template_name: Name of the template (e.g., "Office", "Retail", "Restaurant")
    """
    try:
        templates = load_templates()

        # Normalize the requested template name
        normalized_request = normalize_template_name(template_name)

        # Find matching template
        matching_template = None
        for template in templates:
            if normalize_template_name(template["name"]) == normalized_request:
                matching_template = template
                break

        if not matching_template:
            raise HTTPException(
                status_code=404,
                detail=f"Template '{template_name}' not found. Available templates: {[t['name'] for t in templates]}",
            )

        # Convert to API format
        service_areas = []
        for area in matching_template.get("serviceAreas", []):
            area_id = generate_area_id(area["name"])
            icon = get_area_icon(area["name"])

            tasks = []
            for task_label in area.get("tasks", []):
                task_id = generate_task_id(task_label)
                tasks.append(Task(id=task_id, label=task_label))

            service_areas.append(ServiceArea(id=area_id, name=area["name"], icon=icon, tasks=tasks))

        scope_template = ScopeTemplate(name=matching_template["name"], service_areas=service_areas)

        return TemplateResponse(template=scope_template)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load template: {str(e)}")
