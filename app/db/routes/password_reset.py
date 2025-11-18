from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from .. import schemas, crud
from ..email import send_password_recovery_email
from ..main import get_db

logger = logging.getLogger(__name__)

password_reset_router = APIRouter()

@password_reset_router.post("/api/v1/password-recovery/{email}", response_model=schemas.Message)
def recover_password(email: str, db: Session = Depends(get_db)):
    """
    Request a password reset. Sends an email with a reset token.
    
    Security: Always returns success even if user doesn't exist to prevent email enumeration.
    """
    # Find user by email
    user = crud.get_user_by_email(db, email=email)
    
    # SECURITY: Always return success even if user doesn't exist
    # This prevents email enumeration attacks
    if not user:
        logger.info(f"Password reset requested for non-existent email: {email}")
        return {"message": "If that email exists, a password reset link has been sent"}
    
    # Generate reset token
    try:
        reset_token = crud.create_password_reset_token(db, user_id=user.id)
        
        # Send email with token
        success = send_password_recovery_email(user.email, reset_token.token)
        
        if not success:
            logger.error(f"Failed to send password recovery email to {email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send recovery email. Please contact support."
            )
        
        logger.info(f"Password reset token created for user {user.id}")
        return {"message": "If that email exists, a password reset link has been sent"}
    
    except Exception as e:
        logger.exception(f"Error during password recovery for {email}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during password recovery. Please try again later."
        )

@password_reset_router.post("/api/v1/reset-password/", response_model=schemas.Message)
def reset_password(new_password_data: schemas.NewPassword, db: Session = Depends(get_db)):
    """
    Reset password using a valid token.
    
    Validates the token and updates the user's password if valid.
    """
    # Validate token
    token_record = crud.get_password_reset_token(db, token=new_password_data.token)
    
    if not token_record:
        logger.warning(f"Invalid or expired password reset token attempted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    # Reset the password
    try:
        success = crud.reset_user_password(
            db,
            user_id=token_record.user_id,
            new_password=new_password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password. Please try again."
            )
        
        # Mark token as used
        crud.mark_token_as_used(db, token_id=token_record.id)
        
        logger.info(f"Password reset successful for user {token_record.user_id}")
        return {"message": "Password has been reset successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error during password reset for token {new_password_data.token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting password. Please try again."
        )

