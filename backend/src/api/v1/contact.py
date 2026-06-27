"""Contact form endpoint — publicly accessible, no auth required."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

from src.config import get_settings
from src.infrastructure.email.service import contact_form_email, send_email

router = APIRouter(prefix="/contact", tags=["contact"])


class ContactRequest(BaseModel):
    name:    str  = Field(..., min_length=1, max_length=200)
    email:   EmailStr
    phone:   str | None = Field(None, max_length=50)
    subject: str  = Field(..., min_length=1, max_length=200)
    message: str  = Field(..., min_length=1, max_length=2000)


@router.post("", summary="Submit contact form")
async def submit_contact(req: ContactRequest) -> dict[str, str]:
    """Send the contact form submission as an email to the site owner."""
    settings = get_settings()
    html, text = contact_form_email(
        sender_name=req.name,
        sender_email=str(req.email),
        sender_phone=req.phone,
        subject=req.subject,
        message=req.message,
    )
    await send_email(
        to=settings.email_from,
        subject=f"[OurFamRoots Contact] {req.subject}",
        html_body=html,
        text_body=text,
        reply_to=str(req.email),
    )
    return {"status": "received"}
