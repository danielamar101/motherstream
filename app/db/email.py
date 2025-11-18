import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import datetime

logger = logging.getLogger(__name__)

# Get SMTP configuration from environment
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USER)
DOMAIN = os.environ.get("DOMAIN", "localhost")

def send_test_email(email_to: str) -> bool:
    """Send a test email to verify SMTP configuration"""
    
    # Check if SMTP is configured
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        logger.error("SMTP settings not configured. Cannot send email.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM_EMAIL or SMTP_USER
        msg["To"] = email_to
        msg["Subject"] = "Motherstream - Test Email"

        body = "This is a test email from Motherstream."
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_FROM_EMAIL or SMTP_USER, email_to, text)
        server.quit()

        logger.info(f"Test email sent to {email_to}")
        return True
    except Exception as e:
        logger.exception(f"Failed to send test email to {email_to}: {e}")
        return False

def send_welcome_email(email_to: str, dj_name: str) -> bool:
    """Send welcome email to new users with Discord invite"""
    
    # Check if SMTP is configured
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        logger.error("SMTP settings not configured. Cannot send email.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM_EMAIL or SMTP_USER
        msg["To"] = email_to
        msg["Subject"] = "Welcome to Motherstream! 🎵"
        
        # Discord invite link
        discord_invite = "https://discord.gg/7rXZvjrn"
        
        # Plain text version
        text_body = f"""
Hello {dj_name}!

Welcome to Motherstream - where the beats never stop! 🎵

We're thrilled to have you join our community of DJs and music lovers. Your account has been created successfully and you're ready to start streaming.

Join our Discord community to:
• Connect with other DJs
• Get help and support
• Share your streams
• Stay updated on new features

Join our Discord: {discord_invite}

Ready to start streaming? Log in at https://{DOMAIN}/login

If you have any questions or need help getting started, don't hesitate to reach out!

Happy streaming,
The Motherstream Team
        """
        
        # HTML version
        current_year = datetime.datetime.now().year
        html_body = f"""
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px 40px; text-align: center; background-color: #911c11; border-radius: 8px 8px 0 0;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 32px;">🎵 Motherstream 🎵</h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px;">
                                <h2 style="color: #911c11; margin: 0 0 20px 0; font-size: 28px;">Welcome, {dj_name}!</h2>
                                <p style="color: #333333; line-height: 1.6; margin: 0 0 20px 0; font-size: 16px;">
                                    We're thrilled to have you join our community of DJs and music lovers! 🎉
                                </p>
                                <p style="color: #333333; line-height: 1.6; margin: 0 0 20px 0; font-size: 16px;">
                                    Your account has been created successfully and you're ready to start streaming your incredible sets.
                                </p>
                                
                                <!-- Discord Section -->
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8f8f8; border-radius: 8px; margin: 30px 0;">
                                    <tr>
                                        <td style="padding: 30px; text-align: center;">
                                            <h3 style="color: #5865F2; margin: 0 0 15px 0; font-size: 22px;">Join Our Discord Community!</h3>
                                            <p style="color: #666666; line-height: 1.6; margin: 0 0 20px 0; font-size: 15px;">
                                                Connect with other DJs, get support, and stay updated:
                                            </p>
                                            <ul style="text-align: left; color: #666666; line-height: 2; margin: 0 0 25px 0; padding-left: 20px;">
                                                <li>💬 Chat with fellow DJs</li>
                                                <li>🎧 Share your streams</li>
                                                <li>🆘 Get help and support</li>
                                                <li>📢 Stay updated on features</li>
                                            </ul>
                                            <a href="{discord_invite}" 
                                               style="background-color: #5865F2; 
                                                      color: #ffffff; 
                                                      padding: 14px 30px; 
                                                      text-decoration: none; 
                                                      border-radius: 4px; 
                                                      display: inline-block;
                                                      font-size: 16px;
                                                      font-weight: bold;">
                                                Join Discord Server
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <!-- Get Started Button -->
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
                                    <tr>
                                        <td align="center" style="padding: 20px 0;">
                                            <a href="https://{DOMAIN}/login" 
                                               style="background-color: #911c11; 
                                                      color: #ffffff; 
                                                      padding: 14px 30px; 
                                                      text-decoration: none; 
                                                      border-radius: 4px; 
                                                      display: inline-block;
                                                      font-size: 16px;
                                                      font-weight: bold;">
                                                Start Streaming
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="color: #666666; line-height: 1.6; margin: 20px 0 0 0; font-size: 14px;">
                                    If you have any questions or need help getting started, don't hesitate to reach out!
                                </p>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 20px 40px; background-color: #f8f8f8; border-radius: 0 0 8px 8px; text-align: center;">
                                <p style="color: #999999; margin: 0; font-size: 12px;">
                                    © {current_year} Motherstream. All rights reserved.
                                </p>
                                <p style="color: #999999; margin: 10px 0 0 0; font-size: 11px;">
                                    Where the beats never stop 🎵
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>
        """
        
        # Attach both versions
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL or SMTP_USER, email_to, msg.as_string())
        server.quit()

        logger.info(f"Welcome email sent to {email_to}")
        return True
        
    except Exception as e:
        logger.exception(f"Failed to send welcome email to {email_to}: {e}")
        return False


def send_password_recovery_email(email_to: str, token: str) -> bool:
    """Send password recovery email with reset token"""
    
    # Check if SMTP is configured
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD]):
        logger.error("SMTP settings not configured. Cannot send email.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM_EMAIL or SMTP_USER
        msg["To"] = email_to
        msg["Subject"] = "Motherstream - Password Reset Request"
        
        # Create reset link
        reset_link = f"https://{DOMAIN}/reset-password?token={token}"
        
        # Plain text version
        text_body = f"""
Hello,

You requested to reset your password for Motherstream.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
The Motherstream Team
        """
        
        # HTML version
        current_year = datetime.datetime.now().year
        html_body = f"""
<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f4f4f4; padding: 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="padding: 40px 40px 20px 40px; text-align: center; background-color: #911c11; border-radius: 8px 8px 0 0;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px;">Motherstream</h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px;">
                                <h2 style="color: #911c11; margin: 0 0 20px 0; font-size: 24px;">Password Reset Request</h2>
                                <p style="color: #333333; line-height: 1.6; margin: 0 0 20px 0; font-size: 16px;">
                                    Hello,
                                </p>
                                <p style="color: #333333; line-height: 1.6; margin: 0 0 30px 0; font-size: 16px;">
                                    You requested to reset your password for your Motherstream account. Click the button below to create a new password:
                                </p>
                                <!-- Button -->
                                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td align="center" style="padding: 20px 0;">
                                            <a href="{reset_link}" 
                                               style="background-color: #911c11; 
                                                      color: #ffffff; 
                                                      padding: 14px 30px; 
                                                      text-decoration: none; 
                                                      border-radius: 4px; 
                                                      display: inline-block;
                                                      font-size: 16px;
                                                      font-weight: bold;">
                                                Reset Password
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                <p style="color: #666666; line-height: 1.6; margin: 20px 0 0 0; font-size: 14px;">
                                    Or copy and paste this link into your browser:
                                </p>
                                <p style="color: #911c11; line-height: 1.6; margin: 10px 0 20px 0; font-size: 14px; word-break: break-all;">
                                    {reset_link}
                                </p>
                                <hr style="border: none; border-top: 1px solid #dddddd; margin: 30px 0;">
                                <p style="color: #999999; line-height: 1.6; margin: 0; font-size: 13px;">
                                    <strong>This link will expire in 24 hours.</strong>
                                </p>
                                <p style="color: #999999; line-height: 1.6; margin: 10px 0 0 0; font-size: 13px;">
                                    If you did not request a password reset, please ignore this email or contact support if you have concerns.
                                </p>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 20px 40px; background-color: #f8f8f8; border-radius: 0 0 8px 8px; text-align: center;">
                                <p style="color: #999999; margin: 0; font-size: 12px;">
                                    © {current_year} Motherstream. All rights reserved.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        </body>
    </html>
    """
        
        # Attach both versions
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL or SMTP_USER, email_to, msg.as_string())
        server.quit()
        
        logger.info(f"Password recovery email sent to {email_to}")
        return True
        
    except Exception as e:
        logger.exception(f"Failed to send password recovery email to {email_to}: {e}")
        return False
