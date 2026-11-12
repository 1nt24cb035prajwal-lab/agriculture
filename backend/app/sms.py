import os, httpx


class NotConfigured(Exception):
    pass


async def send_sms(phone: str, text: str):
    sid, tok, frm = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"), os.getenv("TWILIO_FROM")
    if sid and tok and frm:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                             auth=(sid, tok), data={"To": phone, "From": frm, "Body": text})
            r.raise_for_status()
        return
    if os.getenv("APP_ENV", "dev") == "dev":
        print(f"\n[DEV SMS -> {phone}] {text}\n")   # development only; never enabled when APP_ENV=prod
        return
    raise NotConfigured("SMS provider not configured (set TWILIO_* variables).")
