from dataclasses import dataclass
from typing import Any


# ============================================================
# PROTOTYPE WEATHER THRESHOLDS
# ============================================================
#
# These are deterministic research thresholds used to decide
# whether the system should PROCEED or DELAY the advisory.
#
# They are NOT replacements for pesticide-label instructions.
# Product-specific restrictions remain authoritative.
#

RAIN_PROBABILITY_THRESHOLD = 0.60
RAIN_AMOUNT_THRESHOLD_MM = 1.0

HIGH_WIND_THRESHOLD_M_S = 3.0


@dataclass
class WeatherRuleResult:
    status: str
    explanation: str
    fired_rules: list[str]


def evaluate_weather_safety(
    weather: dict[str, Any],
) -> WeatherRuleResult:
    """
    Evaluate whether forecast weather is suitable for continuing
    toward a spray recommendation.

    Possible status:
        proceed
        delay
    """

    fired_rules: list[str] = []

    rain_total_mm = float(
        weather.get(
            "rain_total_mm",
            0.0,
        )
        or 0.0
    )

    max_rain_probability = float(
        weather.get(
            "max_rain_probability",
            0.0,
        )
        or 0.0
    )

    max_wind_speed_m_s = float(
        weather.get(
            "max_wind_speed_m_s",
            0.0,
        )
        or 0.0
    )


    # ========================================================
    # RULE 1 — RAIN
    # ========================================================

    rain_risk = (
        max_rain_probability
        >= RAIN_PROBABILITY_THRESHOLD
        and
        rain_total_mm
        >= RAIN_AMOUNT_THRESHOLD_MM
    )

    if rain_risk:
        fired_rules.append(
            "weather_rain_delay"
        )


    # ========================================================
    # RULE 2 — WIND
    # ========================================================

    wind_risk = (
        max_wind_speed_m_s
        >= HIGH_WIND_THRESHOLD_M_S
    )

    if wind_risk:
        fired_rules.append(
            "weather_high_wind_delay"
        )


    # ========================================================
    # DELAY
    # ========================================================

    if fired_rules:

        reasons = []

        if rain_risk:

            reasons.append(
                (
                    f"Rain risk is elevated "
                    f"({rain_total_mm:.2f} mm forecast; "
                    f"{max_rain_probability * 100:.0f}% "
                    f"maximum precipitation probability)"
                )
            )

        if wind_risk:

            reasons.append(
                (
                    f"forecast wind reaches "
                    f"{max_wind_speed_m_s:.2f} m/s"
                )
            )

        return WeatherRuleResult(
            status="delay",

            explanation=(
                "Weather conditions are not suitable for "
                "automatically continuing to a spray advisory: "
                + "; ".join(reasons)
                + ". Check product-label requirements and "
                  "wait for more suitable application conditions."
            ),

            fired_rules=fired_rules,
        )


    # ========================================================
    # PROCEED
    # ========================================================

    fired_rules.append(
        "weather_conditions_passed"
    )

    return WeatherRuleResult(
        status="proceed",

        explanation=(
            "No configured rain or high-wind weather "
            "constraint was triggered."
        ),

        fired_rules=fired_rules,
    )