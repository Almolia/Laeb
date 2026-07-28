import uuid
import time

import httpx
from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Mock PSP")
payments: dict[str, dict] = {}


class ChargeRequest(BaseModel):
    amountMinor: int = Field(gt=0)
    callbackUrl: str
    reference: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/charge")
def charge(request: ChargeRequest, background: BackgroundTasks) -> dict:
    payment_id = str(uuid.uuid4())
    payments[payment_id] = {"status": "PENDING", **request.model_dump()}

    def callback() -> None:
        # Give Wallet time to commit the PENDING top-up before the bank webhook arrives.
        time.sleep(0.1)
        with httpx.Client(timeout=10) as client:
            response = client.post(
                request.callbackUrl,
                json={
                    "paymentId": payment_id,
                    "reference": request.reference,
                    "status": "SUCCEEDED",
                },
            )
            response.raise_for_status()
        payments[payment_id]["status"] = "SUCCEEDED"

    background.add_task(callback)
    return {
        "paymentId": payment_id,
        "status": "PENDING",
        "redirectUrl": f"http://localhost:8020/pay/{payment_id}",
    }
