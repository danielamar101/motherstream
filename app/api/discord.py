import requests
import os
import logging

logger = logging.getLogger(__name__)

def send_discord_message(message):
    """
    Sends a message to a Discord channel via a webhook URL.

    Args:
        webhook_url (str): The Discord webhook URL.
        message (str): The message to send to the channel.

    Returns:
        response (Response): The response object from the HTTP request.
    """
    try:
        WEBHOOK_URL=os.environ.get("DISCORD_WEBHOOK_URL")
        DISCORD_NOTIF_TOGGLE=os.environ.get("TOGGLE_DISCORD_NOTIFICATIONS")
        if DISCORD_NOTIF_TOGGLE:
            data = {
                "content": message
            }

            response = requests.post(WEBHOOK_URL, json=data)

            if response.status_code == 204:
                logger.info("Message sent successfully!")
            else:
                logger.info(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")

            return response
        else:
            logger.info("Discord notifications have been disabled.")
    except Exception as e:
        logger.error("Error sending discord notif")

if __name__ == "__main__":
    send_discord_message(message="Hello world this is a discord bot test")