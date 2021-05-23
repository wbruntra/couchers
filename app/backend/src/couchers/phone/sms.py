import secrets

import boto3
import luhn

from couchers.config import config


def generate_random_code():
    """Return a random 6-digit string with correct Luhn checksum"""
    # For simplicity we force the string to not have leading zeros
    return luhn.append(str(10000 + secrets.randbelow(90000)))


def format_message(token):
    return "Couchers.org code: " + token + ". If not requested by you, ignore this sms. -- the couchers team"


def send_sms(number, message):
    """Send SMS to a E.164 formatted phone number. Return "success" on
    success, "unsupported operator" on unsupported operator, and any other
    string for any other error."""

    if not config["ENABLE_SMS"]:
        logger.info(f"SMS not emabled, need to send to {number}: {message}")
        return

    if len(request.message) > 140:
        return "message too long"

    sns = boto3.client("sns")
    sns.set_sms_attributes(
        attributes={"DefaultSenderID": config.get("SMS_SENDER_ID"), "DefaultSMSType": "Transactional"}
    )

    response = sns.publish(
        PhoneNumber=number,
        Message=message,
    )

    message_id = response["MessageId"]

    with session_scope() as session:
        session.add(
            Email(
                id=message_id,
                number=number,
                message=message,
            )
        )

    return "success"
