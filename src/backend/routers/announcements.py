"""
Endpoints for managing announcements in the High School Management System API
"""

from datetime import date
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pymongo import ReturnDocument
from pydantic import BaseModel, Field, model_validator

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    start_date: Optional[date] = None
    expires_at: date

    @model_validator(mode="after")
    def check_values(self):
        self.message = self.message.strip()
        if not self.message:
            raise ValueError("Message must not be blank")
        if self.start_date and self.start_date > self.expires_at:
            raise ValueError("Start date must not be after expiration date")
        return self


def _require_teacher(teacher_username: str) -> None:
    if not teachers_collection.find_one({"_id": teacher_username}):
        raise HTTPException(
            status_code=401, detail="Authentication required")


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc["_id"],
        "message": doc["message"],
        "start_date": doc.get("start_date"),
        "expires_at": doc["expires_at"]
    }


def _to_document(data: AnnouncementIn) -> Dict[str, Any]:
    return {
        "message": data.message,
        "start_date": data.start_date.isoformat() if data.start_date else None,
        "expires_at": data.expires_at.isoformat()
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get announcements that are currently active (public)"""
    today = date.today().isoformat()
    docs = announcements_collection.find({
        "expires_at": {"$gte": today},
        "$or": [{"start_date": None}, {"start_date": {"$lte": today}}]
    }).sort("expires_at", 1)
    return [_serialize(d) for d in docs]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str) -> List[Dict[str, Any]]:
    """Get every announcement, including expired and scheduled (signed-in users only)"""
    _require_teacher(teacher_username)
    docs = announcements_collection.find().sort("expires_at", -1)
    return [_serialize(d) for d in docs]


@router.post("", response_model=Dict[str, Any])
def create_announcement(data: AnnouncementIn, teacher_username: str) -> Dict[str, Any]:
    """Create an announcement (signed-in users only)"""
    _require_teacher(teacher_username)
    doc = {"_id": str(ObjectId()), **_to_document(data)}
    announcements_collection.insert_one(doc)
    return _serialize(doc)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str, data: AnnouncementIn, teacher_username: str
) -> Dict[str, Any]:
    """Update an announcement (signed-in users only)"""
    _require_teacher(teacher_username)
    result = announcements_collection.find_one_and_update(
        {"_id": announcement_id},
        {"$set": _to_document(data)},
        return_document=ReturnDocument.AFTER
    )
    if not result:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return _serialize(result)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str) -> Dict[str, str]:
    """Delete an announcement (signed-in users only)"""
    _require_teacher(teacher_username)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted"}
