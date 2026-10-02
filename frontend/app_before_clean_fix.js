"use strict";

document.addEventListener("DOMContentLoaded", function () {

    console.log("KisanSaarthi app.js loaded");

    const form = document.getElementById("advisoryForm");
    const result = document.getElementById("result");
    const button = document.getElementById("submitButton");

    if (!form) {
        console.error("advisoryForm not found");
        return;
    }

    if (!result) {
        console.error("result container not found");
        return;
    }

    function getValue(id) {
        const element = document.getElementById(id);

        if (!element) {
            return "";
        }

        return element.value.trim();
    }

    function getInt(id) {
        const value = getValue(id);

        if (value === "") {
            return null;
        }

        const number = parseInt(value, 10);

        return Number.isNaN(number)
            ? null
            : number;
    }

    function getFloat(id) {
        const value = getValue(id);

        if (value === "") {
            return null;
        }

        const number = parseFloat(value);

        return Number.isNaN(number)
            ? null
            : number;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    }


    form.addEventListener("submit", async function (event) {

        event.preventDefault();

        console.log("Generate button clicked");

        let previousCount =
            getInt("previousApplicationCount");

        let daysSince =
            getInt("daysSinceLastApplication");

        if (previousCount === 0) {
            daysSince = null;
        }

        const payload = {

            farmer_id: null,

            crop:
                getValue("crop"),

            pest:
                getValue("pest"),

            field_area:
                getFloat("fieldArea"),

            area_unit:
                getValue("areaUnit"),

            expected_harvest_days:
                getInt("harvestDays"),

            growth_stage:
                getValue("growthStage") || null,

            previous_application_count:
                previousCount,

            days_since_last_application:
                daysSince,

            state:
                getValue("state") || null,

            district:
                getValue("district") || null,

            latitude:
                getFloat("latitude"),

            longitude:
                getFloat("longitude")
        };


        console.log("Payload:", payload);


        result.innerHTML = `
            <h3>Checking farmer context...</h3>
            <p>Please wait while the advisory is evaluated.</p>
        `;


        if (button) {
            button.disabled = true;
            button.textContent = "Checking...";
        }


        try {

            const response = await fetch(
                "/api/advisory",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(payload),

                    cache:
                        "no-store"
                }
            );


            const data =
                await response.json();


            console.log(
                "Backend response:",
                data
            );


            if (!response.ok) {

                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : JSON.stringify(data.detail)
                );
            }


            const rules =
                Array.isArray(data.fired_rules)
                    ? data.fired_rules
                    : [];


            const rulesHtml =
                rules
                    .map(
                        rule =>
                            `<li>${escapeHtml(rule)}</li>`
                    )
                    .join("");


            result.innerHTML = `

                <h2>
                    Decision:
                    ${escapeHtml(
                        String(
                            data.status
                            || "unknown"
                        ).toUpperCase()
                    )}
                </h2>


                <h3>
                    Advisory Explanation
                </h3>

                <p>
                    ${escapeHtml(
                        data.explanation
                        || "No explanation returned."
                    )}
                </p>


                <h3>
                    Treatment Recommendation
                </h3>

                <p>
                    <strong>
                        Active Ingredient:
                    </strong>

                    ${escapeHtml(
                        data.active_ingredient
                        || "Not issued"
                    )}
                </p>


                <p>
                    <strong>
                        Scaled Dose:
                    </strong>

                    ${
                        data.scaled_dose_min
                        !== null
                        &&
                        data.scaled_dose_min
                        !== undefined

                        ? escapeHtml(
                            data.scaled_dose_min
                            +
                            " "
                            +
                            (
                                data.dose_unit
                                || ""
                            )
                        )

                        : "Not issued"
                    }
                </p>


                <p>
                    <strong>
                        Registry Verified:
                    </strong>

                    ${
                        data.registry_verified
                        ? "Yes"
                        : "No"
                    }
                </p>


                <h3>
                    Fired Rules
                </h3>

                <ul>
                    ${rulesHtml}
                </ul>


                <h3>
                    Context Evaluation
                </h3>

                <p>
                    <strong>
                        Weather:
                    </strong>

                    ${escapeHtml(
                        data.weather_status
                        || "Not evaluated"
                    )}
                </p>


                <p>
                    <strong>
                        Soil:
                    </strong>

                    ${escapeHtml(
                        data.soil_status
                        || "Not evaluated"
                    )}
                </p>
            `;


        } catch (error) {

            console.error(
                "Advisory error:",
                error
            );


            result.innerHTML = `

                <h3 style="color:red;">
                    Unable to generate advisory
                </h3>

                <p>
                    ${escapeHtml(
                        error.message
                    )}
                </p>
            `;

        } finally {

            if (button) {

                button.disabled = false;

                button.textContent =
                    "Generate Personalized Advisory";
            }
        }

    });

});