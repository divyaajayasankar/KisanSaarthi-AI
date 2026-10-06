from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.services.weather_service import (
    WeatherServiceError,
    get_location_weather,
)


router = APIRouter(
    prefix="/api/weather",
    tags=["weather"],
)


@router.get("/forecast")
def get_forecast(
    district: str = Query(
        ...,
        min_length=2,
    ),
    state: str = Query(
        ...,
        min_length=2,
    ),
):
    """
    Return a summarized 24-hour weather forecast
    for an Indian district/state.
    """

    try:

        return get_location_weather(
            district=district,
            state=state,
        )

    except WeatherServiceError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Weather service is currently unavailable."
            ),
        ) from exc
