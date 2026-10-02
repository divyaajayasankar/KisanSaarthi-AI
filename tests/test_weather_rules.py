from app.services.weather_rules import (
    evaluate_weather_safety,
)


def test_safe_weather_proceeds():

    weather = {
        "rain_total_mm": 0.0,
        "max_rain_probability": 0.10,
        "max_wind_speed_m_s": 1.5,
    }

    result = evaluate_weather_safety(
        weather
    )

    assert result.status == "proceed"

    assert (
        "weather_conditions_passed"
        in result.fired_rules
    )


def test_rain_causes_delay():

    weather = {
        "rain_total_mm": 2.5,
        "max_rain_probability": 0.80,
        "max_wind_speed_m_s": 1.5,
    }

    result = evaluate_weather_safety(
        weather
    )

    assert result.status == "delay"

    assert (
        "weather_rain_delay"
        in result.fired_rules
    )


def test_high_wind_causes_delay():

    weather = {
        "rain_total_mm": 0.0,
        "max_rain_probability": 0.10,
        "max_wind_speed_m_s": 4.0,
    }

    result = evaluate_weather_safety(
        weather
    )

    assert result.status == "delay"

    assert (
        "weather_high_wind_delay"
        in result.fired_rules
    )


def test_rain_and_wind_both_fire():

    weather = {
        "rain_total_mm": 5.0,
        "max_rain_probability": 0.90,
        "max_wind_speed_m_s": 5.0,
    }

    result = evaluate_weather_safety(
        weather
    )

    assert result.status == "delay"

    assert (
        "weather_rain_delay"
        in result.fired_rules
    )

    assert (
        "weather_high_wind_delay"
        in result.fired_rules
    )


def test_high_rain_probability_without_rain_amount_does_not_delay():

    weather = {
        "rain_total_mm": 0.0,
        "max_rain_probability": 0.90,
        "max_wind_speed_m_s": 1.0,
    }

    result = evaluate_weather_safety(
        weather
    )

    assert result.status == "proceed"


def test_small_rain_amount_does_not_delay():

    weather = {
        "rain_total_mm": 0.2,
        "max_rain_probability": 0.80,
        "max_wind_speed_m_s": 1.0,
    }

    result = evaluate_weather_safety(
        weather
    )

    assert result.status == "proceed"