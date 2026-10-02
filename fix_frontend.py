from pathlib import Path
import shutil


ROOT = Path(r"C:\farmer")
FRONTEND = ROOT / "frontend"

INDEX = FRONTEND / "index.html"
APPJS = FRONTEND / "app.js"


# ============================================================
# BACKUP OLD FILES
# ============================================================

if INDEX.exists():
    shutil.copy2(
        INDEX,
        FRONTEND / "index_before_clean_fix.html"
    )

if APPJS.exists():
    shutil.copy2(
        APPJS,
        FRONTEND / "app_before_clean_fix.js"
    )


# ============================================================
# CLEAN HTML
# ============================================================

html = r"""<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>KisanSaarthi AI</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: #f3f7f2;
            color: #253129;
        }

        .container {
            width: min(1150px, 94%);
            margin: auto;
            padding: 30px 0 50px;
        }

        .hero {
            background: #225f35;
            color: white;
            padding: 30px;
            border-radius: 18px;
            margin-bottom: 24px;
        }

        .hero h1 {
            margin: 0 0 8px;
            font-size: 40px;
        }

        .hero p {
            line-height: 1.6;
            margin: 6px 0;
        }

        .status {
            margin-top: 15px;
            font-weight: bold;
        }

        .layout {
            display: grid;
            grid-template-columns: 1.05fr 0.95fr;
            gap: 22px;
            align-items: start;
        }

        .card {
            background: white;
            border: 1px solid #d6e0d4;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
        }

        .card h2 {
            margin-top: 0;
            color: #225f35;
        }

        .section-title {
            margin-top: 26px;
            margin-bottom: 14px;
            padding-bottom: 8px;
            border-bottom: 1px solid #dce5da;
            color: #225f35;
            font-weight: bold;
            font-size: 17px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }

        .field {
            display: flex;
            flex-direction: column;
            gap: 7px;
        }

        label {
            font-weight: bold;
            font-size: 14px;
        }

        input,
        select {
            width: 100%;
            min-height: 44px;
            padding: 10px 12px;
            border: 1px solid #c7d3c5;
            border-radius: 8px;
            background: white;
            font-size: 15px;
        }

        input:focus,
        select:focus {
            outline: none;
            border-color: #26713c;
        }

        input:disabled {
            background: #eeeeee;
        }

        .help {
            color: #6c786e;
            font-size: 12px;
            line-height: 1.5;
        }

        .buttons {
            margin-top: 24px;
        }

        button {
            border: none;
            border-radius: 9px;
            padding: 12px 18px;
            font-weight: bold;
            cursor: pointer;
        }

        .primary {
            background: #26713c;
            color: white;
        }

        button:disabled {
            opacity: 0.6;
        }

        .decision {
            display: inline-block;
            padding: 10px 16px;
            border-radius: 25px;
            font-weight: bold;
            margin-bottom: 15px;
        }

        .recommend {
            background: #e8f7ed;
            color: #176532;
        }

        .delay {
            background: #fff5d6;
            color: #7c5400;
        }

        .abstain {
            background: #fff0f0;
            color: #a21d1d;
        }

        .unknown {
            background: #eeeeee;
            color: #333333;
        }

        .result-section {
            margin-top: 18px;
            padding-top: 15px;
            border-top: 1px solid #dddddd;
        }

        .result-section h3 {
            margin-top: 0;
        }

        .loading {
            padding: 20px;
            background: #f7faf6;
            border-radius: 10px;
        }

        .error {
            padding: 15px;
            color: #9e1d1d;
            background: #fff0f0;
            border: 1px solid #e4aaaa;
            border-radius: 10px;
        }

        .flow {
            padding: 10px;
            text-align: center;
            background: #f7faf6;
            border: 1px solid #d9e2d7;
            border-radius: 8px;
            margin-bottom: 7px;
            font-weight: bold;
        }

        .arrow {
            text-align: center;
            margin: 5px;
        }

        @media (max-width: 850px) {

            .layout {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 600px) {

            .form-grid {
                grid-template-columns: 1fr;
            }
        }

    </style>

</head>


<body>

<main class="container">


    <section class="hero">

        <h1>KisanSaarthi AI</h1>

        <p>
            Personalized, Evidence-Grounded and Farmer-Centric
            Crop Advisory
        </p>

        <p>
            Verified crop-pest registry, field-area dose calculation,
            harvest safety, growth-stage verification, previous
            treatment history, weather and soil context.
        </p>

        <div class="status">

            System Status:
            <span id="apiStatus">Checking</span>

        </div>

    </section>


    <div class="layout">


        <section class="card">

            <h2>
                Tell Us About Your Field
            </h2>


            <form id="advisoryForm">


                <div class="section-title">
                    Crop and Problem
                </div>


                <div class="form-grid">


                    <div class="field">

                        <label for="crop">
                            Crop Name
                        </label>

                        <input
                            id="crop"
                            type="text"
                            value="Rice"
                            required
                        >

                    </div>


                    <div class="field">

                        <label for="pest">
                            Pest / Disease
                        </label>

                        <input
                            id="pest"
                            type="text"
                            value="Blast; Sheath blight"
                            required
                        >

                    </div>


                </div>



                <div class="section-title">
                    Field and Harvest Context
                </div>


                <div class="form-grid">


                    <div class="field">

                        <label for="fieldArea">
                            Field Area
                        </label>

                        <input
                            id="fieldArea"
                            type="number"
                            min="0.0001"
                            step="any"
                            value="0.5"
                            required
                        >

                    </div>


                    <div class="field">

                        <label for="areaUnit">
                            Area Unit
                        </label>

                        <select
                            id="areaUnit"
                            required
                        >

                            <option value="">
                                Select unit
                            </option>

                            <option
                                value="hectare"
                                selected
                            >
                                Hectare
                            </option>

                            <option value="acre">
                                Acre
                            </option>

                            <option value="cent">
                                Cent
                            </option>

                            <option value="guntha">
                                Guntha
                            </option>

                            <option value="square_metre">
                                Square metre
                            </option>

                        </select>

                    </div>


                    <div class="field">

                        <label for="harvestDays">
                            Days Until Expected Harvest
                        </label>

                        <input
                            id="harvestDays"
                            type="number"
                            min="0"
                            step="1"
                            value="40"
                            required
                        >

                        <span class="help">
                            Used for Pre-Harvest Interval verification.
                        </span>

                    </div>


                    <div class="field">

                        <label for="growthStage">
                            Crop Growth Stage
                        </label>

                        <select id="growthStage">

                            <option value="">
                                Select growth stage
                            </option>

                            <option value="sowing">
                                Sowing
                            </option>

                            <option value="seedling">
                                Seedling
                            </option>

                            <option
                                value="vegetative"
                                selected
                            >
                                Vegetative
                            </option>

                            <option value="reproductive">
                                Flowering / Reproductive
                            </option>

                            <option value="pre_harvest">
                                Pre-Harvest
                            </option>

                        </select>

                    </div>


                </div>



                <div class="section-title">
                    Previous Treatment History
                </div>


                <div class="form-grid">


                    <div class="field">

                        <label for="previousApplicationCount">
                            Previous Application Count
                        </label>

                        <input
                            id="previousApplicationCount"
                            type="number"
                            min="0"
                            step="1"
                            value="3"
                        >

                        <span class="help">
                            Enter 0 if the treatment has not been used before.
                        </span>

                    </div>


                    <div class="field">

                        <label for="daysSinceLastApplication">
                            Days Since Last Application
                        </label>

                        <input
                            id="daysSinceLastApplication"
                            type="number"
                            min="0"
                            step="1"
                        >

                        <span
                            id="daysSinceHelp"
                            class="help"
                        >
                            Optional when no verified repeat interval exists.
                        </span>

                    </div>


                </div>



                <div class="section-title">
                    Location
                </div>


                <div class="form-grid">


                    <div class="field">

                        <label for="state">
                            State
                        </label>

                        <input
                            id="state"
                            type="text"
                            value="Tamil Nadu"
                        >

                    </div>


                    <div class="field">

                        <label for="district">
                            District
                        </label>

                        <input
                            id="district"
                            type="text"
                            value="Coimbatore"
                        >

                    </div>


                    <div class="field">

                        <label for="latitude">
                            Latitude
                        </label>

                        <input
                            id="latitude"
                            type="number"
                            step="any"
                            value="11.0168"
                        >

                    </div>


                    <div class="field">

                        <label for="longitude">
                            Longitude
                        </label>

                        <input
                            id="longitude"
                            type="number"
                            step="any"
                            value="76.9558"
                        >

                    </div>


                </div>



                <div class="buttons">

                    <button
                        id="submitButton"
                        class="primary"
                        type="submit"
                    >
                        Generate Personalized Advisory
                    </button>

                </div>


            </form>

        </section>



        <aside>


            <section class="card">

                <h2>
                    KisanSaarthi Advisory
                </h2>


                <div id="result">

                    <p>
                        Ready to check your field.
                    </p>

                </div>

            </section>



            <section class="card">

                <h2>
                    How KisanSaarthi AI Works
                </h2>

                <div class="flow">
                    Farmer Context
                </div>

                <div class="arrow">v</div>

                <div class="flow">
                    Verified Registry
                </div>

                <div class="arrow">v</div>

                <div class="flow">
                    PHI and Dose
                </div>

                <div class="arrow">v</div>

                <div class="flow">
                    Growth Stage
                </div>

                <div class="arrow">v</div>

                <div class="flow">
                    Previous Treatment History
                </div>

                <div class="arrow">v</div>

                <div class="flow">
                    Weather and Soil
                </div>

                <div class="arrow">v</div>

                <div class="flow">
                    Recommend / Delay / Abstain
                </div>

            </section>


        </aside>


    </div>


</main>


<script src="/static/app.js?v=clean20260920"></script>

</body>

</html>
"""


# ============================================================
# CLEAN JAVASCRIPT
# ============================================================

javascript = r""""use strict";

document.addEventListener("DOMContentLoaded", function () {

    const form =
        document.getElementById("advisoryForm");

    const result =
        document.getElementById("result");

    const button =
        document.getElementById("submitButton");

    const apiStatus =
        document.getElementById("apiStatus");

    const countInput =
        document.getElementById(
            "previousApplicationCount"
        );

    const daysInput =
        document.getElementById(
            "daysSinceLastApplication"
        );

    const daysHelp =
        document.getElementById(
            "daysSinceHelp"
        );


    function value(id) {

        const element =
            document.getElementById(id);

        if (!element) {
            return "";
        }

        return String(
            element.value || ""
        ).trim();
    }


    function integer(id) {

        const raw =
            value(id);

        if (raw === "") {
            return null;
        }

        const number =
            Number.parseInt(
                raw,
                10
            );

        return Number.isNaN(number)
            ? null
            : number;
    }


    function numberValue(id) {

        const raw =
            value(id);

        if (raw === "") {
            return null;
        }

        const number =
            Number.parseFloat(raw);

        return Number.isNaN(number)
            ? null
            : number;
    }


    function escapeHtml(text) {

        return String(
            text ?? ""
        )
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }


    async function checkHealth() {

        try {

            const response =
                await fetch(
                    "/health",
                    {
                        cache: "no-store"
                    }
                );

            if (!response.ok) {
                throw new Error(
                    "Health check failed"
                );
            }

            apiStatus.textContent =
                "Online";

        }
        catch (error) {

            apiStatus.textContent =
                "Offline";

            console.error(error);
        }
    }


    function updateHistoryFields() {

        const raw =
            countInput.value.trim();

        if (raw === "") {

            daysInput.disabled =
                false;

            daysHelp.textContent =
                "Optional when no verified repeat interval exists.";

            return;
        }


        const count =
            Number.parseInt(
                raw,
                10
            );


        if (count === 0) {

            daysInput.value =
                "";

            daysInput.disabled =
                true;

            daysHelp.textContent =
                "Not applicable because there were no previous applications.";

        }
        else {

            daysInput.disabled =
                false;

            daysHelp.textContent =
                "Optional when no verified repeat interval exists.";
        }
    }


    function renderResult(data) {

        const status =
            String(
                data.status || "unknown"
            ).toLowerCase();


        const statusText =
            status.toUpperCase();


        const validStatuses =
            [
                "recommend",
                "delay",
                "abstain"
            ];


        const statusClass =
            validStatuses.includes(status)
            ? status
            : "unknown";


        let dose =
            "Not issued";


        if (
            data.scaled_dose_min !== null
            &&
            data.scaled_dose_min !== undefined
        ) {

            dose =
                String(
                    data.scaled_dose_min
                );


            if (
                data.scaled_dose_max !== null
                &&
                data.scaled_dose_max !== undefined
                &&
                data.scaled_dose_max
                !==
                data.scaled_dose_min
            ) {

                dose +=
                    " - "
                    +
                    data.scaled_dose_max;
            }


            if (data.dose_unit) {

                dose +=
                    " "
                    +
                    data.dose_unit;
            }
        }


        const rules =
            Array.isArray(
                data.fired_rules
            )
            ? data.fired_rules
            : [];


        const ruleItems =
            rules
                .map(
                    rule =>
                        "<li>"
                        +
                        escapeHtml(rule)
                        +
                        "</li>"
                )
                .join("");


        result.innerHTML = `

            <div class="decision ${statusClass}">
                ${escapeHtml(statusText)}
            </div>


            <div class="result-section">

                <h3>
                    Advisory Explanation
                </h3>

                <p>
                    ${
                        escapeHtml(
                            data.explanation
                            ||
                            "No explanation returned."
                        )
                    }
                </p>

            </div>


            <div class="result-section">

                <h3>
                    Treatment Recommendation
                </h3>

                <p>
                    <strong>
                        Active Ingredient:
                    </strong>

                    ${
                        escapeHtml(
                            data.active_ingredient
                            ||
                            "Not issued"
                        )
                    }
                </p>


                <p>
                    <strong>
                        Scaled Dose:
                    </strong>

                    ${escapeHtml(dose)}
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

            </div>


            <div class="result-section">

                <h3>
                    Fired Rules
                </h3>

                ${
                    ruleItems
                    ? "<ul>" + ruleItems + "</ul>"
                    : "<p>No rules returned.</p>"
                }

            </div>


            <div class="result-section">

                <h3>
                    Context Evaluation
                </h3>

                <p>
                    <strong>
                        Weather:
                    </strong>

                    ${
                        escapeHtml(
                            data.weather_status
                            ||
                            "Not evaluated"
                        )
                    }
                </p>


                <p>
                    <strong>
                        Soil:
                    </strong>

                    ${
                        escapeHtml(
                            data.soil_status
                            ||
                            "Not evaluated"
                        )
                    }
                </p>

            </div>
        `;
    }


    form.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            let previousCount =
                integer(
                    "previousApplicationCount"
                );


            let daysSince =
                integer(
                    "daysSinceLastApplication"
                );


            if (previousCount === 0) {
                daysSince = null;
            }


            const payload = {

                farmer_id: null,

                crop:
                    value("crop"),

                pest:
                    value("pest"),

                field_area:
                    numberValue(
                        "fieldArea"
                    ),

                area_unit:
                    value(
                        "areaUnit"
                    ),

                expected_harvest_days:
                    integer(
                        "harvestDays"
                    ),

                growth_stage:
                    value(
                        "growthStage"
                    )
                    ||
                    null,

                previous_application_count:
                    previousCount,

                days_since_last_application:
                    daysSince,

                state:
                    value("state")
                    ||
                    null,

                district:
                    value("district")
                    ||
                    null,

                latitude:
                    numberValue(
                        "latitude"
                    ),

                longitude:
                    numberValue(
                        "longitude"
                    )
            };


            console.log(
                "Sending advisory request:",
                payload
            );


            result.innerHTML = `

                <div class="loading">

                    <strong>
                        Checking farmer context...
                    </strong>

                    <br><br>

                    Evaluating registry, dose,
                    harvest safety, growth stage,
                    treatment history, weather
                    and soil.

                </div>
            `;


            button.disabled =
                true;

            button.textContent =
                "Checking Advisory...";


            try {

                const response =
                    await fetch(
                        "/api/advisory",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify(
                                    payload
                                ),

                            cache:
                                "no-store"
                        }
                    );


                const text =
                    await response.text();


                let data;


                try {

                    data =
                        JSON.parse(text);

                }
                catch (error) {

                    throw new Error(
                        "Invalid server response: "
                        +
                        text
                    );
                }


                if (!response.ok) {

                    throw new Error(
                        typeof data.detail === "string"
                        ? data.detail
                        : JSON.stringify(
                            data.detail
                            ||
                            data
                        )
                    );
                }


                console.log(
                    "Advisory response:",
                    data
                );


                renderResult(data);

            }
            catch (error) {

                console.error(error);


                result.innerHTML = `

                    <div class="error">

                        <strong>
                            Unable to generate advisory.
                        </strong>

                        <br><br>

                        ${escapeHtml(
                            error.message
                        )}

                    </div>
                `;

            }
            finally {

                button.disabled =
                    false;

                button.textContent =
                    "Generate Personalized Advisory";
            }
        }
    );


    countInput.addEventListener(
        "input",
        updateHistoryFields
    );


    updateHistoryFields();

    checkHealth();


    console.log(
        "KisanSaarthi clean frontend loaded."
    );

});
"""


# ============================================================
# WRITE BOTH FILES AS REAL UTF-8
# ============================================================

FRONTEND.mkdir(
    parents=True,
    exist_ok=True
)


with open(
    INDEX,
    "w",
    encoding="utf-8",
    newline="\n"
) as file:

    file.write(html)


with open(
    APPJS,
    "w",
    encoding="utf-8",
    newline="\n"
) as file:

    file.write(javascript)


print("")
print("CLEAN FRONTEND CREATED")
print("----------------------")
print("index.html:", INDEX)
print("app.js:", APPJS)
print("")
print(
    "Old frontend files were backed up."
)