"""Stands in for a real bank gateway. Card data never reaches our services:
the client posts to the PSP, the PSP calls our webhook back with a reference."""
import uuid

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

app = FastAPI(title="mock-psp")
PAYMENTS: dict[str, dict] = {}


class ChargeRequest(BaseModel):
    amountMinor: int
    callbackUrl: str
    reference: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/charge")
def charge(req: ChargeRequest, bg: BackgroundTasks):
    payment_id = str(uuid.uuid4())
    PAYMENTS[payment_id] = {"status": "PENDING", **req.model_dump()}

    def callback():
        with httpx.Client(timeout=10) as c:
            c.post(
                req.callbackUrl,
                json={
                    "paymentId": payment_id,
                    "reference": req.reference,
                    "status": "SUCCEEDED",
                },
            )
        PAYMENTS[payment_id]["status"] = "SUCCEEDED"

    bg.add_task(callback)
    return {
        "paymentId": payment_id,
        "status": "PENDING",
        "redirectUrl": f"http://localhost:8020/pay/{payment_id}",
    }


@app.get("/pay/{payment_id}")
def pay_page(payment_id: str):
    payment = PAYMENTS.get(payment_id)
    if not payment:
        return {"status": "NOT_FOUND"}
    return {"paymentId": payment_id, **payment}
