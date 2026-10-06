// C:\farmer\frontend\app.js

const API_BASE = "";


// ============================================================
// DOM HELPERS
// ============================================================

function byId(id) {

    return document.getElementById(
        id
    );
}


function getTextValue(id) {

    const element = byId(
        id
    );

    if (!element) {
        return "";
    }

    return element.value.trim();
}


function getNullableInteger(id) {

    const value = getTextValue(
        id
    );

    if (value === "") {
        return null;
    }

    const parsed =
        Number.parseInt(
            value,
            10
        );

    return Number.isNaN(
        parsed
    )
        ? null
        : parsed;
}


function getNullableFloat(id) {

    const value = getTextValue(
        id
    );

    if (value === "") {
        return null;
    }

    const parsed =
        Number.parseFloat(
            value
        );

    return Number.isNaN(
        parsed
    )
        ? null
        : parsed;
}


// ============================================================
// DISPLAY HELPERS
// ============================================================

function escapeHtml(value) {

    if (
        value === null
        ||
        value === undefined
    ) {

        return "";
    }


    return String(value)

        .replaceAll(
            "&",
            "&amp;"
        )

        .replaceAll(
            "<",
            "&lt;"
        )

        .replaceAll(
            ">",
            "&gt;"
        )

        .replaceAll(
            '"',
            "&quot;"
        )

        .replaceAll(
            "'",
            "&#039;"
        );
}


function prettyRule(rule) {

    return String(
        rule || ""
    )

        .replaceAll(
            "_",
            " "
        )

        .replace(
            /\b\w/g,
            char =>
                char.toUpperCase()
        );
}


function displayValue(
    value,
    emptyText = "Not evaluated",
) {

    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {

        return emptyText;
    }


    return escapeHtml(
        value
    );
}


// ============================================================
// CLEAN INITIAL SCREEN
// ============================================================

function clearFarmerInputs() {

    const ids = [

        "farmerQuestion",

        "crop",

        "pest",

        "fieldArea",

        "harvestDays",

        "previousApplicationCount",

        "daysSinceLastApplication",

        "state",

        "district",

        "latitude",

        "longitude",
    ];


    ids.forEach(
        id => {

            const element =
                byId(id);

            if (element) {

                element.value = "";
            }
        }
    );


    const areaUnit =
        byId(
            "areaUnit"
        );


    if (areaUnit) {

        areaUnit.selectedIndex = 0;
    }


    const growthStage =
        byId(
            "growthStage"
        );


    if (growthStage) {

        growthStage.selectedIndex = 0;
    }


    const locationStatus =
        byId(
            "locationStatus"
        );


    if (locationStatus) {

        locationStatus.textContent = "";
    }


    const ragResult =
        byId(
            "ragResult"
        );


    if (ragResult) {

        ragResult.style.display =
            "none";

        ragResult.innerHTML = "";
    }


    updateTreatmentHistoryControls();
}


// ============================================================
// RESET RESULT
// ============================================================

function resetAdvisoryResult() {

    const result =
        byId(
            "result"
        );


    if (result) {

        result.innerHTML = `

            <div class="result-empty">

                <div>

                    <div class="big-icon">

                        🌱

                    </div>

                    <strong>

                        Ready to check your field

                    </strong>

                    <p>

                        Enter the farmer context
                        and generate an advisory.

                    </p>

                </div>

            </div>

        `;
    }


    const error =
        byId(
            "formError"
        );


    if (error) {

        error.classList.remove(
            "show"
        );

        error.textContent = "";
    }
}


// ============================================================
// CLEAR EVERYTHING
// ============================================================

function clearEverything() {

    clearFarmerInputs();

    resetAdvisoryResult();
}


// ============================================================
// HEALTH CHECK
// ============================================================

async function checkHealth() {

    const apiStatus =
        byId(
            "apiStatus"
        );


    if (!apiStatus) {

        return;
    }


    apiStatus.textContent =
        "Checking";


    try {

        const response =
            await fetch(
                `${API_BASE}/health`,
                {
                    cache:
                        "no-store",
                }
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );
        }


        apiStatus.textContent =
            "Online";

    }

    catch (error) {

        apiStatus.textContent =
            "Unavailable";
    }
}


// ============================================================
// TREATMENT HISTORY UI
// ============================================================

function updateTreatmentHistoryControls() {

    const countInput =
        byId(
            "previousApplicationCount"
        );


    const daysInput =
        byId(
            "daysSinceLastApplication"
        );


    const help =
        byId(
            "daysSinceHelp"
        );


    if (
        !countInput
        ||
        !daysInput
    ) {

        return;
    }


    const rawCount =
        countInput.value.trim();


    // --------------------------------------------------------
    // NO VALUE ENTERED
    // --------------------------------------------------------

    if (
        rawCount === ""
    ) {

        daysInput.disabled =
            false;


        if (help) {

            help.textContent =
                "Optional. Used only when a verified repeat interval is available.";
        }


        return;
    }


    const count =
        Number.parseInt(
            rawCount,
            10
        );


    // --------------------------------------------------------
    // NO PREVIOUS APPLICATION
    // --------------------------------------------------------

    if (
        count === 0
    ) {

        daysInput.value = "";

        daysInput.disabled =
            true;


        if (help) {

            help.textContent =
                "Not applicable because there were no previous applications.";
        }


        return;
    }


    // --------------------------------------------------------
    // PREVIOUS APPLICATION EXISTS
    // --------------------------------------------------------

    daysInput.disabled =
        false;


    if (help) {

        help.textContent =
            "Enter this only when the treatment has been used before.";
    }
}


// ============================================================
// LIVE LOCATION
// ============================================================

function captureLiveLocation() {

    const button =
        byId(
            "getLiveLocationButton"
        );


    const status =
        byId(
            "locationStatus"
        );


    const latitude =
        byId(
            "latitude"
        );


    const longitude =
        byId(
            "longitude"
        );


    // --------------------------------------------------------
    // GEOLOCATION NOT AVAILABLE
    // --------------------------------------------------------

    if (
        !navigator.geolocation
    ) {

        if (status) {

            status.textContent =
                "Live location is not supported by this browser.";
        }


        return;
    }


    // --------------------------------------------------------
    // START
    // --------------------------------------------------------

    if (button) {

        button.disabled = true;

        button.textContent =
            "📍 Detecting...";
    }


    if (status) {

        status.textContent =
            "Requesting your device location. Allow browser location permission.";
    }


    navigator.geolocation
        .getCurrentPosition(

            // =================================================
            // SUCCESS
            // =================================================

            position => {

                const lat =
                    position
                        .coords
                        .latitude;


                const lon =
                    position
                        .coords
                        .longitude;


                if (latitude) {

                    latitude.value =
                        lat.toFixed(
                            6
                        );
                }


                if (longitude) {

                    longitude.value =
                        lon.toFixed(
                            6
                        );
                }


                if (status) {

                    status.textContent =
                        "✓ Live coordinates captured. State and district remain editable.";
                }


                if (button) {

                    button.disabled =
                        false;

                    button.textContent =
                        "📍 Use My Live Location";
                }
            },


            // =================================================
            // ERROR
            // =================================================

            error => {

                let message =
                    "Unable to retrieve your live location.";


                if (
                    error.code
                    ===
                    error.PERMISSION_DENIED
                ) {

                    message =
                        "Location permission was denied. Allow location access or enter coordinates manually.";
                }


                else if (
                    error.code
                    ===
                    error.POSITION_UNAVAILABLE
                ) {

                    message =
                        "Your current location is unavailable. Enter coordinates manually.";
                }


                else if (
                    error.code
                    ===
                    error.TIMEOUT
                ) {

                    message =
                        "Location request timed out. Try again or enter coordinates manually.";
                }


                if (status) {

                    status.textContent =
                        message;
                }


                if (button) {

                    button.disabled =
                        false;

                    button.textContent =
                        "📍 Use My Live Location";
                }
            },


            // =================================================
            // OPTIONS
            // =================================================

            {
                enableHighAccuracy:
                    true,

                timeout:
                    15000,

                maximumAge:
                    0,
            }
        );
}


// ============================================================
// RAG RESULT RENDERING
// ============================================================

function renderRagResult(
    data
) {

    const container =
        byId(
            "ragResult"
        );


    if (!container) {

        return;
    }


    const results =
        Array.isArray(
            data.results
        )

            ? data.results

            : [];


    container.style.display =
        "block";


    // --------------------------------------------------------
    // NO EVIDENCE
    // --------------------------------------------------------

    if (
        data.status
        !==
        "retrieved"

        ||

        results.length === 0
    ) {

        container.innerHTML = `

            <strong>

                No verified evidence retrieved

            </strong>

            <p class="muted">

                ${escapeHtml(
                    data.explanation
                    ||
                    "No sufficiently relevant verified evidence was found."
                )}

            </p>

        `;


        return;
    }


    // --------------------------------------------------------
    // EVIDENCE CARDS
    // --------------------------------------------------------

    const cards =
        results
            .map(
                (
                    item,
                    index
                ) => `

                    <div class="rag-evidence">

                        <strong>

                            Evidence ${index + 1}

                        </strong>


                        <div
                            class="result-grid"
                            style="margin-top:10px;"
                        >

                            <div class="key">
                                Crop
                            </div>

                            <div>
                                ${escapeHtml(
                                    item.crop
                                    || ""
                                )}
                            </div>


                            <div class="key">
                                Topic
                            </div>

                            <div>
                                ${escapeHtml(
                                    item.topic
                                    || ""
                                )}
                            </div>


                            <div class="key">
                                Category
                            </div>

                            <div>
                                ${escapeHtml(
                                    item.category
                                    || ""
                                )}
                            </div>


                            <div class="key">
                                Source
                            </div>

                            <div>
                                ${escapeHtml(
                                    item.source
                                    || ""
                                )}
                            </div>


                            <div class="key">
                                Verified
                            </div>

                            <div>

                                ${
                                    item.verified
                                        ? "Yes"
                                        : "No"
                                }

                            </div>

                        </div>


                        <p
                            class="muted"
                            style="margin-bottom:0;"
                        >

                            ${escapeHtml(
                                item.text
                                || ""
                            )}

                        </p>

                    </div>

                `
            )

            .join("");


    container.innerHTML = `

        <div>

            <strong>

                Verified Evidence Retrieved

            </strong>


            <p class="muted">

                ${escapeHtml(
                    data.explanation
                    ||
                    `Retrieved ${results.length} verified evidence item(s).`
                )}

            </p>


            ${cards}

        </div>

    `;
}


// ============================================================
// RAG SEARCH
// ============================================================

async function searchVerifiedKnowledge() {

    const button =
        byId(
            "ragSearchButton"
        );


    const question =
        getTextValue(
            "farmerQuestion"
        );


    const crop =
        getTextValue(
            "crop"
        );


    const container =
        byId(
            "ragResult"
        );


    // --------------------------------------------------------
    // QUESTION REQUIRED
    // --------------------------------------------------------

    if (!question) {

        if (container) {

            container.style.display =
                "block";


            container.innerHTML = `

                <strong>

                    Enter a farmer question first.

                </strong>

                <p class="muted">

                    Example:
                    How can I manage blast in my rice crop?

                </p>

            `;
        }


        return;
    }


    // --------------------------------------------------------
    // LOADING STATE
    // --------------------------------------------------------

    if (button) {

        button.disabled = true;

        button.textContent =
            "Searching...";
    }


    if (container) {

        container.style.display =
            "block";


        container.innerHTML = `

            <span class="muted">

                Searching verified agricultural evidence...

            </span>

        `;
    }


    try {

        const response =
            await fetch(

                `${API_BASE}/api/rag/search`,

                {
                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json",
                    },

                    body:
                        JSON.stringify(
                            {
                                query:
                                    question,

                                crop:
                                    crop
                                    || null,

                                top_k:
                                    3,
                            }
                        ),
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(

                typeof data.detail
                ===
                "string"

                    ? data.detail

                    : (
                        "RAG search failed "
                        +
                        `with HTTP ${response.status}.`
                    )
            );
        }


        renderRagResult(
            data
        );

    }

    catch (error) {

        if (container) {

            container.style.display =
                "block";


            container.innerHTML = `

                <strong>

                    Unable to search verified knowledge.

                </strong>

                <p class="muted">

                    ${escapeHtml(
                        error.message
                    )}

                </p>

            `;
        }

    }

    finally {

        if (button) {

            button.disabled =
                false;


            button.textContent =
                "🔎 Search Verified Knowledge";
        }
    }
}


// ============================================================
// RESULT RENDERING
// ============================================================

function renderResult(
    data
) {

    const container =
        byId(
            "result"
        );


    if (!container) {

        return;
    }


    const status =
        String(
            data.status
            ||
            "unknown"
        )
        .toLowerCase();


    const statusClass = [

        "recommend",

        "delay",

        "abstain",

    ].includes(
        status
    )

        ? status

        : "unknown";


    // --------------------------------------------------------
    // DOSE
    // --------------------------------------------------------

    let doseText =
        "Not issued";


    if (
        data.scaled_dose_min
        !==
        null

        &&

        data.scaled_dose_min
        !==
        undefined
    ) {

        if (
            data.scaled_dose_max
            !==
            null

            &&

            data.scaled_dose_max
            !==
            undefined

            &&

            data.scaled_dose_max
            !==
            data.scaled_dose_min
        ) {

            doseText =

                `${escapeHtml(
                    data.scaled_dose_min
                )} – `

                +

                `${escapeHtml(
                    data.scaled_dose_max
                )} `

                +

                `${escapeHtml(
                    data.dose_unit
                    || ""
                )}`;

        }

        else {

            doseText =

                `${escapeHtml(
                    data.scaled_dose_min
                )} `

                +

                `${escapeHtml(
                    data.dose_unit
                    || ""
                )}`;
        }
    }


    // --------------------------------------------------------
    // ACTIVE INGREDIENT
    // --------------------------------------------------------

    const activeIngredient =

        data.active_ingredient
        !==
        null

        &&

        data.active_ingredient
        !==
        undefined

            ? escapeHtml(
                data.active_ingredient
            )

            : "Not issued";


    // --------------------------------------------------------
    // RULES
    // --------------------------------------------------------

    const rules =

        Array.isArray(
            data.fired_rules
        )

            ? data.fired_rules

            : [];


    const ruleHtml =

        rules.length

            ? `

                <ul class="rule-list">

                    ${
                        rules
                            .map(
                                rule => `

                                    <li>

                                        ${escapeHtml(
                                            prettyRule(
                                                rule
                                            )
                                        )}

                                    </li>

                                `
                            )
                            .join("")
                    }

                </ul>

            `

            : `

                <p class="muted">

                    No fired rules returned.

                </p>

            `;


    // --------------------------------------------------------
    // RESULT HEADING
    // --------------------------------------------------------

    let heading =
        "Advisory Result";


    if (
        status
        ===
        "recommend"
    ) {

        heading =
            "Recommendation is eligible";
    }


    else if (
        status
        ===
        "delay"
    ) {

        heading =
            "Wait for safer conditions";
    }


    else if (
        status
        ===
        "abstain"
    ) {

        heading =
            "More verified context is needed";
    }


    // --------------------------------------------------------
    // FINAL UI
    // --------------------------------------------------------

    container.innerHTML = `

        <div
            class="decision ${statusClass}"
        >

            ${escapeHtml(
                status.toUpperCase()
            )}

        </div>


        <h3
            style="
                margin-top:14px;
                font-size:24px;
            "
        >

            ${heading}

        </h3>


        <div class="result-section">

            <h3>
                Why this decision?
            </h3>


            <p
                class="muted"
                style="color:var(--text);"
            >

                ${escapeHtml(
                    data.explanation
                    ||
                    "No explanation returned."
                )}

            </p>

        </div>


        <div class="result-section">

            <h3>

                Treatment Recommendation

            </h3>


            <div class="result-grid">

                <div class="key">

                    Active Ingredient

                </div>

                <div>

                    ${activeIngredient}

                </div>


                <div class="key">

                    Scaled Dose

                </div>

                <div>

                    ${doseText}

                </div>


                <div class="key">

                    Registry Verified

                </div>

                <div>

                    ${
                        data.registry_verified
                            ? "Yes"
                            : "No"
                    }

                </div>

            </div>

        </div>


        <div class="result-section">

            <h3>

                Context Evaluation

            </h3>


            <div class="context-pills">

                <span class="context-pill">

                    Weather:
                    ${displayValue(
                        data.weather_status
                    )}

                </span>


                <span class="context-pill">

                    Soil:
                    ${displayValue(
                        data.soil_status
                    )}

                </span>

            </div>

        </div>


        <div class="result-section">

            <h3>

                Fired Rules

            </h3>


            ${ruleHtml}

        </div>

    `;
}


// ============================================================
// ERROR DISPLAY
// ============================================================

function showFormError(
    message
) {

    const errorBox =
        byId(
            "formError"
        );


    if (!errorBox) {

        return;
    }


    errorBox.textContent =
        message;


    errorBox.classList.add(
        "show"
    );
}


function clearFormError() {

    const errorBox =
        byId(
            "formError"
        );


    if (!errorBox) {

        return;
    }


    errorBox.textContent = "";


    errorBox.classList.remove(
        "show"
    );
}


// ============================================================
// ADVISORY SUBMISSION
// ============================================================

async function submitAdvisory(
    event
) {

    event.preventDefault();


    clearFormError();


    // --------------------------------------------------------
    // REQUIRED INPUTS
    // --------------------------------------------------------

    const crop =
        getTextValue(
            "crop"
        );


    const pest =
        getTextValue(
            "pest"
        );


    const fieldArea =
        getNullableFloat(
            "fieldArea"
        );


    const areaUnit =
        getTextValue(
            "areaUnit"
        );


    const harvestDays =
        getNullableInteger(
            "harvestDays"
        );


    // --------------------------------------------------------
    // BASIC FRONTEND VALIDATION
    // --------------------------------------------------------

    if (
        !crop
        ||
        !pest
    ) {

        showFormError(
            "Enter both Crop Name and Pest / Disease."
        );

        return;
    }


    if (
        fieldArea === null
        ||
        fieldArea <= 0
    ) {

        showFormError(
            "Enter a valid field area greater than 0."
        );

        return;
    }


    if (!areaUnit) {

        showFormError(
            "Select the field area unit."
        );

        return;
    }


    if (
        harvestDays === null
        ||
        harvestDays < 0
    ) {

        showFormError(
            "Enter valid days until expected harvest."
        );

        return;
    }


    // --------------------------------------------------------
    // TREATMENT HISTORY
    // --------------------------------------------------------

    const previousApplicationCount =

        getNullableInteger(
            "previousApplicationCount"
        );


    let daysSinceLastApplication =

        getNullableInteger(
            "daysSinceLastApplication"
        );


    if (
        previousApplicationCount
        ===
        0
    ) {

        daysSinceLastApplication =
            null;
    }


    // --------------------------------------------------------
    // BUILD API REQUEST
    // --------------------------------------------------------

    const payload = {

        farmer_id:
            null,


        crop:
            crop,


        pest:
            pest,


        field_area:
            fieldArea,


        area_unit:
            areaUnit,


        expected_harvest_days:
            harvestDays,


        growth_stage:

            getTextValue(
                "growthStage"
            )

            || null,


        previous_application_count:
            previousApplicationCount,


        days_since_last_application:
            daysSinceLastApplication,


        state:

            getTextValue(
                "state"
            )

            || null,


        district:

            getTextValue(
                "district"
            )

            || null,


        latitude:

            getNullableFloat(
                "latitude"
            ),


        longitude:

            getNullableFloat(
                "longitude"
            ),
    };


    const submitButton =
        byId(
            "submitButton"
        );


    const result =
        byId(
            "result"
        );


    // --------------------------------------------------------
    // LOADING UI
    // --------------------------------------------------------

    if (submitButton) {

        submitButton.disabled =
            true;


        submitButton.textContent =
            "Evaluating verified evidence...";
    }


    if (result) {

        result.innerHTML = `

            <div class="result-empty">

                <div>

                    <div class="big-icon">

                        ⏳

                    </div>


                    <strong>

                        Checking your field context

                    </strong>


                    <p>

                        Evaluating registry, dose,
                        PHI, growth stage,
                        treatment history,
                        resistance, weather
                        and soil.

                    </p>

                </div>

            </div>

        `;
    }


    try {

        const response =
            await fetch(

                `${API_BASE}/api/advisory`,

                {
                    method:
                        "POST",

                    headers: {

                        "Content-Type":
                            "application/json",
                    },

                    body:
                        JSON.stringify(
                            payload
                        ),
                }
            );


        let data = null;


        try {

            data =
                await response.json();
        }

        catch (error) {

            data = null;
        }


        if (!response.ok) {

            let message =

                "Advisory request failed "
                +
                `with HTTP ${response.status}.`;


            if (
                data
                &&
                data.detail
            ) {

                message =

                    typeof data.detail
                    ===
                    "string"

                        ? data.detail

                        : JSON.stringify(
                            data.detail
                        );
            }


            throw new Error(
                message
            );
        }


        renderResult(
            data
        );

    }

    catch (error) {

        resetAdvisoryResult();


        showFormError(

            error.message

            ||

            "Unable to generate advisory."
        );
    }

    finally {

        if (submitButton) {

            submitButton.disabled =
                false;


            submitButton.textContent =
                "✨ Generate Personalized Advisory";
        }
    }
}


// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener(

    "DOMContentLoaded",

    () => {

        // ----------------------------------------------------
        // ALWAYS START BLANK
        // ----------------------------------------------------

        clearEverything();


        // ----------------------------------------------------
        // HEALTH
        // ----------------------------------------------------

        checkHealth();


        // ----------------------------------------------------
        // TREATMENT HISTORY
        // ----------------------------------------------------

        const previousCount =
            byId(
                "previousApplicationCount"
            );


        if (previousCount) {

            previousCount
                .addEventListener(

                    "input",

                    updateTreatmentHistoryControls
                );
        }


        // ----------------------------------------------------
        // LIVE LOCATION
        // ----------------------------------------------------

        const locationButton =
            byId(
                "getLiveLocationButton"
            );


        if (locationButton) {

            locationButton
                .addEventListener(

                    "click",

                    captureLiveLocation
                );
        }


        // ----------------------------------------------------
        // VERIFIED RAG
        // ----------------------------------------------------

        const ragButton =
            byId(
                "ragSearchButton"
            );


        if (ragButton) {

            ragButton
                .addEventListener(

                    "click",

                    searchVerifiedKnowledge
                );
        }


        // ----------------------------------------------------
        // CLEAR
        // ----------------------------------------------------

        const clearButton =
            byId(
                "clearButton"
            );


        if (clearButton) {

            clearButton
                .addEventListener(

                    "click",

                    clearEverything
                );
        }


        // ----------------------------------------------------
        // ADVISORY FORM
        // ----------------------------------------------------

        const form =
            byId(
                "advisoryForm"
            );


        if (form) {

            form
                .addEventListener(

                    "submit",

                    submitAdvisory
                );
        }
    }
);


// ============================================================
// CLEAR BROWSER RESTORED VALUES
// ============================================================

window.addEventListener(

    "pageshow",

    event => {

        if (
            event.persisted
        ) {

            clearEverything();

            checkHealth();
        }
    }
);