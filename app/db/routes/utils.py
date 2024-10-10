from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas, crud
from ..email import send_test_email
from ..main import get_db

util_router = APIRouter()

@util_router.post("/test-email/", response_model=schemas.Message)
def test_email(email_to: str, db: Session = Depends(get_db)):
    # Implement email sending logic
    success = send_test_email(email_to)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to send test email")
    return {"message": "Test email sent successfully"}

@util_router.get("/health-check/", response_model=bool)
def health_check():
    # Implement health check logic, e.g., db connectivity
    # Here, we simply return True
    return True