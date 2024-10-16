import requests
import os
import logging

logger = logging.getLogger(__name__)

def send_discord_message(message):
    WEBHOOK_URL=os.environ.get("DISCORD_WEBHOOK_URL")
    """
    Sends a message to a Discord channel via a webhook URL.

    Args:
        webhook_url (str): The Discord webhook URL.
        message (str): The message to send to the channel.

    Returns:
        response (Response): The response object from the HTTP request.
    """
    data = {
        "content": message
    }

    response = requests.post(WEBHOOK_URL, json=data)

    if response.status_code == 204:
        logger.info("Message sent successfully!")
    else:
        logger.info(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")

    return response

if __name__ == "__main__":
    send_discord_message(message="Hello world this is a discord bot test")