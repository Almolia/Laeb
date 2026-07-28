from fastapi import APIRouter

router = APIRouter(tags=["ops"])
_readiness_checks: list = []


def register_readiness_check(fn) -> None:
    _readiness_checks.append(fn)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    failures = []
    for fn in _readiness_checks:
        try:
            fn()
        except Exception as exc:
            failures.append(f"{fn.__name__}: {exc}")
    if failures:
        return {"status": "degraded", "failures": failures}
    return {"status": "ready"}
