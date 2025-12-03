from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """
    Very simple health check endpoint.

    You can open this in your browser to quickly ensure the backend is running.
    """
    return {"status": "ok"}


