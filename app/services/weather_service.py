import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()


OPENWEATHER_API_KEY = os.getenv(
    "OPENWEATHER_API_KEY"
)

GEOCODING_URL = (
    "https://api.openweathermap.org/geo/1.0/direct"
)

FORECAST_URL = (
    "https://api.openweathermap.org/data/2.5/forecast"
)


class WeatherServiceError(Exception):
    """Raised when weather information cannot be retrieved."""
    pass


def _get_api_key() -> str:
    """
    Return the configured OpenWeather API key.

    The API key is never hard-coded in source code.
    """

    if not OPENWEATHER_API_KEY:
        raise WeatherServiceError(
            "OPENWEATHER_API_KEY is not configured."
        )

    return OPENWEATHER_API_KEY


def geocode_location(
    district: str,
    state: str,
) -> dict[str, Any]:
    """
    Convert district/state to latitude and longitude.

    Example:
        Chennai, Tamil Nadu, India
            ->
        latitude / longitude
    """

    api_key = _get_api_key()

    district = district.strip()
    state = state.strip()

    if not district:
        raise WeatherServiceError(
            "District is required."
        )

    # First try a more specific query.
    query_candidates = [
        f"{district},{state},IN"
        if state
        else f"{district},IN",
        f"{district},IN",
    ]

    with httpx.Client(timeout=15.0) as client:

        for query in query_candidates:

            response = client.get(
                GEOCODING_URL,
                params={
                    "q": query,
                    "limit": 5,
                    "appid": api_key,
                },
            )

            response.raise_for_status()

            locations = response.json()

            if not locations:
                continue

            # Prefer an Indian result.
            indian_results = [
                item
                for item in locations
                if item.get("country") == "IN"
            ]

            selected = (
                indian_results[0]
                if indian_results
                else locations[0]
            )

            return {
                "name": selected.get(
                    "name",
                    district,
                ),
                "state": selected.get(
                    "state",
                    state,
                ),
                "country": selected.get(
                    "country",
                    "IN",
                ),
                "latitude": float(
                    selected["lat"]
                ),
                "longitude": float(
                    selected["lon"]
                ),
            }

    raise WeatherServiceError(
        f"Could not find coordinates for "
        f"{district}, {state}."
    )


def get_weather_forecast(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    """
    Retrieve the OpenWeather 5-day / 3-hour forecast.
    """

    api_key = _get_api_key()

    try:

        with httpx.Client(
            timeout=20.0
        ) as client:

            response = client.get(
                FORECAST_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "appid": api_key,
                    "units": "metric",
                },
            )

            response.raise_for_status()

            return response.json()

    except httpx.HTTPStatusError as exc:

        raise WeatherServiceError(
            "OpenWeather returned an HTTP error: "
            f"{exc.response.status_code}"
        ) from exc

    except httpx.RequestError as exc:

        raise WeatherServiceError(
            "Unable to connect to OpenWeather."
        ) from exc


def summarize_next_24_hours(
    forecast_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Summarize the first 24 hours of forecast data.

    OpenWeather 5-day forecast uses approximately
    3-hour intervals, so 8 entries represent 24 hours.
    """

    forecast_list = forecast_data.get(
        "list",
        []
    )

    if not forecast_list:
        raise WeatherServiceError(
            "Forecast response contains no weather data."
        )

    next_24h = forecast_list[:8]

    total_rain_mm = 0.0

    max_rain_probability = 0.0

    max_wind_speed_m_s = 0.0

    temperatures = []

    weather_conditions = []


    for item in next_24h:

        # --------------------------------------------
        # Rain amount
        # --------------------------------------------

        rain = item.get(
            "rain",
            {}
        )

        total_rain_mm += float(
            rain.get(
                "3h",
                0.0,
            )
        )


        # --------------------------------------------
        # Probability of precipitation
        # --------------------------------------------

        probability = float(
            item.get(
                "pop",
                0.0,
            )
        )

        max_rain_probability = max(
            max_rain_probability,
            probability,
        )


        # --------------------------------------------
        # Wind
        # --------------------------------------------

        wind_speed = float(
            item.get(
                "wind",
                {}
            ).get(
                "speed",
                0.0,
            )
        )

        max_wind_speed_m_s = max(
            max_wind_speed_m_s,
            wind_speed,
        )


        # --------------------------------------------
        # Temperature
        # --------------------------------------------

        temperature = (
            item.get(
                "main",
                {}
            ).get(
                "temp"
            )
        )

        if temperature is not None:
            temperatures.append(
                float(temperature)
            )


        # --------------------------------------------
        # Conditions
        # --------------------------------------------

        weather_items = item.get(
            "weather",
            []
        )

        if weather_items:

            description = weather_items[0].get(
                "description"
            )

            if (
                description
                and
                description
                not in weather_conditions
            ):
                weather_conditions.append(
                    description
                )


    city = forecast_data.get(
        "city",
        {}
    )


    return {

        "forecast_window_hours": 24,

        "rain_total_mm": round(
            total_rain_mm,
            2,
        ),

        "max_rain_probability": round(
            max_rain_probability,
            3,
        ),

        "max_wind_speed_m_s": round(
            max_wind_speed_m_s,
            2,
        ),

        "min_temperature_c": (
            round(
                min(temperatures),
                2,
            )
            if temperatures
            else None
        ),

        "max_temperature_c": (
            round(
                max(temperatures),
                2,
            )
            if temperatures
            else None
        ),

        "conditions": weather_conditions,

        "city": city.get(
            "name"
        ),

        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


def get_location_weather(
    district: str,
    state: str,
) -> dict[str, Any]:
    """
    Complete weather workflow:

        district/state
            ->
        coordinates
            ->
        forecast
            ->
        24-hour weather summary
    """

    location = geocode_location(
        district=district,
        state=state,
    )

    forecast = get_weather_forecast(
        latitude=location[
            "latitude"
        ],
        longitude=location[
            "longitude"
        ],
    )

    summary = summarize_next_24_hours(
        forecast
    )

    return {
        "location": location,
        "weather": summary,
        "source": "OpenWeather",
    }