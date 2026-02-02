"""
Webhook endpoints.

Handles incoming webhooks from Stripe and Telegram.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.payments import get_stripe_service, StripeService
from app.services.notifications import get_telegram_bot, TelegramBot


router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe: StripeService = Depends(get_stripe_service),
):
    """
    Handle Stripe webhook events.

    Stripe sends events for subscription changes, successful payments, etc.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    try:
        result = stripe.handle_webhook(db, payload, sig_header)
        return result
    except ValueError as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
    telegram: TelegramBot = Depends(get_telegram_bot),
):
    """
    Handle Telegram webhook updates.

    Telegram sends updates when users interact with the bot.
    Set this URL in Telegram using:
    https://api.telegram.org/bot<TOKEN>/setWebhook?url=<YOUR_URL>/api/v1/webhooks/telegram
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        )

    # Extract message info
    message = data.get("message", {})
    chat = message.get("chat", {})
    text = message.get("text", "")
    chat_id = str(chat.get("id", ""))
    username = message.get("from", {}).get("username")

    if not chat_id or not text:
        return {"ok": True}  # Ignore non-text messages

    # Parse command
    if text.startswith("/"):
        parts = text.split()
        command = parts[0][1:].lower()  # Remove / and lowercase
        args = parts[1:] if len(parts) > 1 else []

        response = telegram.handle_command(
            db=db,
            chat_id=chat_id,
            command=command,
            args=args,
            username=username,
        )

        # Send response
        telegram.send_message(chat_id, response)

    return {"ok": True}


@router.get("/telegram/set-webhook")
async def set_telegram_webhook(
    url: str,
    telegram: TelegramBot = Depends(get_telegram_bot),
):
    """
    Set the Telegram webhook URL.

    Call this once during deployment to configure the bot.
    The URL should be: https://your-domain.com/api/v1/webhooks/telegram

    Security note: In production, protect this endpoint or remove it.
    """
    import httpx

    # Call Telegram API to set webhook
    response = httpx.get(
        f"https://api.telegram.org/bot{telegram.token}/setWebhook",
        params={"url": url},
    )

    result = response.json()

    if result.get("ok"):
        logger.info(f"Telegram webhook set to: {url}")
        return {"success": True, "url": url}
    else:
        logger.error(f"Failed to set webhook: {result}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("description", "Failed to set webhook"),
        )
