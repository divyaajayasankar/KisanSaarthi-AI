from pathlib import Path
import re


HTML_FILE = Path(
    r"C:\farmer\frontend\index.html"
)

BACKUP_FILE = Path(
    r"C:\farmer\frontend\index_before_phase9_rag.html"
)


# ============================================================
# LOAD CURRENT FRONTEND
# ============================================================

text = HTML_FILE.read_text(
    encoding="utf-8"
)


# ============================================================
# BACKUP
# ============================================================

BACKUP_FILE.write_text(
    text,
    encoding="utf-8"
)


# ============================================================
# RAG CSS
# ============================================================

rag_css = """

        /* =====================================================
           PHASE 9 - VERIFIED RAG
        ====================================================== */

        textarea {
            width: 100%;
            min-height: 110px;
            padding: 10px 12px;
            border: 1px solid #c8d5c6;
            border-radius: 9px;
            background: white;
            font-size: 15px;
            font-family: Arial, Helvetica, sans-serif;
            resize: vertical;
        }

        textarea:focus {
            outline: none;
            border-color: #2d7842;
            box-shadow:
                0 0 0 3px
                rgba(
                    45,
                    120,
                    66,
                    0.10
                );
        }

        .rag-button {
            margin-top: 10px;

            background: #edf4ee;

            color: #205b32;

            border:
                1px solid #c8d5c6;
        }

        .rag-button:hover {
            background: #e2eee4;
        }

        .rag-result {
            display: none;

            margin-top: 16px;

            padding: 15px;

            border:
                1px solid #d8e3d6;

            border-radius: 10px;

            background: #f8faf7;
        }

        .rag-evidence {
            margin-top: 15px;

            padding-top: 15px;

            border-top:
                1px solid #d8e3d6;
        }

"""


if "PHASE 9 - VERIFIED RAG" not in text:

    if "</style>" not in text:

        raise RuntimeError(
            "Could not find </style> in index.html"
        )

    text = text.replace(
        "</style>",
        rag_css + "\n    </style>",
        1
    )


# ============================================================
# RAG HTML
# ============================================================

rag_html = """

                <!-- =================================================
                     PHASE 9 - VERIFIED AGRICULTURAL RAG
                ================================================== -->

                <div class="section-title">
                    Farmer Question - Verified Knowledge Search
                </div>


                <div class="form-grid">


                    <div class="field field-full">


                        <label for="farmerQuestion">
                            Ask KisanSaarthi
                        </label>


                        <textarea
                            id="farmerQuestion"
                            name="farmerQuestion"
                            rows="4"
                            placeholder="Example: How can I manage blast in my rice crop?"
                            autocomplete="off"
                        ></textarea>


                        <span class="help">

                            Searches only the verified
                            agricultural knowledge base.

                        </span>


                        <button
                            id="ragSearchButton"
                            class="rag-button"
                            type="button"
                        >
                            Search Verified Knowledge
                        </button>


                        <div
                            id="ragResult"
                            class="rag-result"
                        ></div>


                    </div>


                </div>

"""


# ============================================================
# INSERT BEFORE "CROP AND PROBLEM"
# ============================================================

if 'id="farmerQuestion"' not in text:

    crop_pattern = re.compile(
        r'<div\s+class=["\']section-title["\']\s*>\s*'
        r'Crop\s+and\s+Problem\s*'
        r'</div>',
        flags=re.IGNORECASE
    )

    match = crop_pattern.search(
        text
    )

    if not match:

        raise RuntimeError(
            'Could not find the "Crop and Problem" section '
            'inside C:\\farmer\\frontend\\index.html'
        )

    insert_position = (
        match.start()
    )

    text = (
        text[:insert_position]
        + rag_html
        + text[insert_position:]
    )


# ============================================================
# INLINE RAG JAVASCRIPT
# ============================================================

rag_javascript = r"""

<script id="phase9RagScript">

document.addEventListener(
    "DOMContentLoaded",
    function () {

        const ragButton =
            document.getElementById(
                "ragSearchButton"
            );

        const questionInput =
            document.getElementById(
                "farmerQuestion"
            );

        const cropInput =
            document.getElementById(
                "crop"
            );

        const ragResult =
            document.getElementById(
                "ragResult"
            );


        if (
            !ragButton
            ||
            !questionInput
            ||
            !ragResult
        ) {

            console.error(
                "Phase 9 RAG elements not found."
            );

            return;
        }


        function escapeHtml(
            value
        ) {

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


        ragButton.addEventListener(
            "click",

            async function () {

                const query =
                    questionInput
                        .value
                        .trim();


                const crop =
                    cropInput
                    ? cropInput.value.trim()
                    : "";


                ragResult.style.display =
                    "block";


                if (!query) {

                    ragResult.innerHTML = `

                        <div class="error">

                            Please enter a farmer question.

                        </div>
                    `;

                    return;
                }


                ragButton.disabled =
                    true;


                ragButton.textContent =
                    "Searching...";


                ragResult.innerHTML = `

                    <div class="loading">

                        Searching verified agricultural
                        knowledge...

                    </div>
                `;


                try {

                    const response =
                        await fetch(
                            "/api/rag/search",
                            {

                                method:
                                    "POST",

                                headers: {

                                    "Content-Type":
                                        "application/json"

                                },

                                body:
                                    JSON.stringify(
                                        {

                                            query:
                                                query,

                                            crop:
                                                crop || null,

                                            top_k:
                                                3

                                        }
                                    )

                            }
                        );


                    const data =
                        await response.json();


                    console.log(
                        "RAG response:",
                        data
                    );


                    if (!response.ok) {

                        throw new Error(
                            data.detail
                            ||
                            "RAG API request failed."
                        );
                    }


                    if (
                        data.status !==
                            "retrieved"
                        ||
                        !Array.isArray(
                            data.results
                        )
                        ||
                        data.results.length === 0
                    ) {

                        ragResult.innerHTML = `

                            <strong>
                                No verified evidence found.
                            </strong>

                            <p>
                                ${escapeHtml(
                                    data.explanation
                                    ||
                                    ""
                                )}
                            </p>
                        `;

                        return;
                    }


                    let html = `

                        <div
                            class="decision recommend"
                        >
                            VERIFIED EVIDENCE RETRIEVED
                        </div>


                        <div class="rag-evidence">

                            <strong>
                                Retrieval Summary
                            </strong>

                            <p>
                                ${escapeHtml(
                                    data.explanation
                                    ||
                                    ""
                                )}
                            </p>

                        </div>
                    `;


                    data.results.forEach(
                        function (
                            item,
                            index
                        ) {

                            html += `

                                <div class="rag-evidence">

                                    <h3>
                                        Evidence ${index + 1}
                                    </h3>


                                    <p>

                                        <strong>
                                            Crop:
                                        </strong>

                                        ${escapeHtml(
                                            item.crop
                                            ||
                                            "Not specified"
                                        )}

                                    </p>


                                    <p>

                                        <strong>
                                            Topic:
                                        </strong>

                                        ${escapeHtml(
                                            item.topic
                                            ||
                                            "Not specified"
                                        )}

                                    </p>


                                    <p>

                                        <strong>
                                            Category:
                                        </strong>

                                        ${escapeHtml(
                                            item.category
                                            ||
                                            "Not specified"
                                        )}

                                    </p>


                                    <p>

                                        <strong>
                                            Source:
                                        </strong>

                                        ${escapeHtml(
                                            item.source
                                            ||
                                            "Not specified"
                                        )}

                                    </p>


                                    <p>

                                        <strong>
                                            Source Type:
                                        </strong>

                                        ${escapeHtml(
                                            item.source_type
                                            ||
                                            "Not specified"
                                        )}

                                    </p>


                                    <p>

                                        <strong>
                                            Verified:
                                        </strong>

                                        ${
                                            item.verified
                                            ? "Yes"
                                            : "No"
                                        }

                                    </p>


                                    <p>

                                        <strong>
                                            Supporting Evidence:
                                        </strong>

                                    </p>


                                    <p>

                                        ${escapeHtml(
                                            item.text
                                            ||
                                            ""
                                        )}

                                    </p>

                                </div>
                            `;
                        }
                    );


                    ragResult.innerHTML =
                        html;

                }
                catch (error) {

                    console.error(
                        "RAG error:",
                        error
                    );


                    ragResult.innerHTML = `

                        <div class="error">

                            <strong>
                                RAG Error
                            </strong>

                            <p>
                                ${escapeHtml(
                                    error.message
                                )}
                            </p>

                        </div>
                    `;

                }
                finally {

                    ragButton.disabled =
                        false;


                    ragButton.textContent =
                        "Search Verified Knowledge";
                }

            }
        );

    }
);

</script>

"""


if 'id="phase9RagScript"' not in text:

    if "</body>" not in text:

        raise RuntimeError(
            "Could not find </body> in index.html"
        )

    text = text.replace(
        "</body>",
        rag_javascript
        + "\n</body>",
        1
    )


# ============================================================
# SAVE
# ============================================================

HTML_FILE.write_text(
    text,
    encoding="utf-8"
)


# ============================================================
# VERIFY
# ============================================================

updated_text = (
    HTML_FILE.read_text(
        encoding="utf-8"
    )
)


farmer_question_ok = (
    'id="farmerQuestion"'
    in updated_text
)

rag_button_ok = (
    'id="ragSearchButton"'
    in updated_text
)

rag_script_ok = (
    'id="phase9RagScript"'
    in updated_text
)


print()
print(
    "Updated:",
    HTML_FILE
)

print(
    "farmerQuestion present:",
    farmer_question_ok
)

print(
    "ragSearchButton present:",
    rag_button_ok
)

print(
    "RAG JavaScript present:",
    rag_script_ok
)


if not (
    farmer_question_ok
    and
    rag_button_ok
    and
    rag_script_ok
):

    raise RuntimeError(
        "Phase 9 RAG frontend update failed."
    )


print()
print(
    "PHASE 9 RAG FRONTEND UPDATE SUCCESSFUL"
)