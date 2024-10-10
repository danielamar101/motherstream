import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .schemas import User

def send_test_email(email_to: str) -> bool:
    try:
        # Configure your SMTP server details
        smtp_server = "smtp.example.com"
        smtp_port = 587
        smtp_user = "your_email@example.com"
        smtp_password = "your_password"

        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = email_to
        msg["Subject"] = "Test Email"

        body = "This is a test email."
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_user, email_to, text)
        server.quit()

        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def send_password_recovery_email(email_to: str, token: str) -> bool:
    try:
        # Implement password recovery email sending logic with token
        smtp_server = "smtp.example.com"
        smtp_port = 587
        smtp_user = "your_email@example.com"
        smtp_password = "your_password"

        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = email_to
        msg["Subject"] = "Password Recovery"

        recovery_link = f"https://yourdomain.com/reset-password?token={token}"
        body = f"Click the link below to reset your password:\n{recovery_link}"
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_user, email_to, text)
        server.quit()

        return True
    except Exception as e:
        print(f"Failed to send password recovery email: {e}")
        return False

def generate_password_recovery_html(user: User) -> str:
    # Generate HTML content for password recovery
    recovery_link = f"https://yourdomain.com/reset-password?user_id={user.id}"
    html_content = f"""
    <html>
        <body>
            <p>Hello {user.dj_name or user.email},</p>
            <p>Click the link below to reset your password:</p>
            <a href="{recovery_link}">Reset Password</a>
        </body>
    </html>
    """
    return html_content