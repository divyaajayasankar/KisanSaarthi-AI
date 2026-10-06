# C:\farmer\app\routers\agent.py

from typing import Optional, Any

from fastapi import (
    APIRouter,
    Depends,
)

from pydantic import (
    BaseModel,
    Field,
)

from sqlalchemy.orm import Session

from app.db import get_db

from app.schemas import (
    AdvisoryRequest,
)

from app.routers.advisory import (
    get_advisory,
)

from app.services.agent_orchestrator import (
    plan_farmer_query,
)

from app.services.agent_executor import (
    execute_specialist,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/agent",
    tags=["Agentic Orchestration"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class AgentQueryRequest(BaseModel):

    question: str = Field(
        ...,
        min_length=2,
    )

    crop: Optional[str] = None

    pest: Optional[str] = None

    field_area: Optional[float] = None

    area_unit: Optional[str] = None

    expected_harvest_days: Optional[int] = None

    growth_stage: Optional[str] = None

    previous_application_count: Optional[int] = None

    days_since_last_application: Optional[int] = None

    state: Optional[str] = None

    district: Optional[str] = None

    latitude: Optional[float] = None

    longitude: Optional[float] = None


# ============================================================
# BUILD AGENT PLAN
# ============================================================

def build_plan(
    request: AgentQueryRequest,
) -> dict[str, Any]:

    return plan_farmer_query(

        question=request.question,

        crop=request.crop,

        pest=request.pest,

        field_area=request.field_area,

        area_unit=request.area_unit,

        expected_harvest_days=(
            request.expected_harvest_days
        ),

        growth_stage=request.growth_stage,

        previous_application_count=(
            request.previous_application_count
        ),

        days_since_last_application=(
            request.days_since_last_application
        ),

        state=request.state,

        district=request.district,

        latitude=request.latitude,

        longitude=request.longitude,
    )


# ============================================================
# PHASE 10A
# PLAN ONLY
# ============================================================

@router.post("/query")
def agent_query(
    request: AgentQueryRequest,
):

    return build_plan(
        request
    )


# ============================================================
# PHASE 10B + 10C
# PLAN + EXECUTE
# ============================================================

@router.post("/execute")
def agent_execute(
    request: AgentQueryRequest,
    db: Session = Depends(get_db),
):

    # ========================================================
    # STEP 1 â€” UNDERSTAND QUESTION
    # ========================================================

    plan = build_plan(
        request
    )


    # ========================================================
    # STEP 2 â€” CHECK MISSING CONTEXT
    # ========================================================

    if plan["missing_context"]:

        return {

            "execution_status":
                "needs_context",

            "intent":
                plan["intent"],

            "selected_tools":
                plan["selected_tools"],

            "missing_context":
                plan["missing_context"],

            "message": (
                "Additional farmer context is required "
                "before the selected specialist tools "
                "can be executed."
            ),

            "agent_plan":
                plan,

            "result":
                None,
        }


    # ========================================================
    # STEP 3 â€” FULL ADVISORY EXECUTION
    # ========================================================

    if plan["intent"] == "advisory":

        crop = (
            plan["entities"].get("crop")
            or request.crop
        )

        pest = (
            plan["entities"].get("pest")
            or request.pest
        )


        if not crop or not pest:

            missing = []

            if not crop:
                missing.append(
                    "crop"
                )

            if not pest:
                missing.append(
                    "pest"
                )


            return {

                "execution_status":
                    "needs_context",

                "intent":
                    "advisory",

                "selected_tools":
                    plan["selected_tools"],

                "missing_context":
                    missing,

                "message": (
                    "Crop and pest/disease "
                    "information are required."
                ),

                "agent_plan":
                    plan,

                "result":
                    None,
            }


        # ----------------------------------------------------
        # Reuse existing deterministic advisory engine.
        # Safety-critical logic is NOT duplicated here.
        # ----------------------------------------------------

        advisory_request = AdvisoryRequest(

            farmer_id=None,

            crop=crop,

            pest=pest,

            field_area=(
                request.field_area
            ),

            area_unit=(
                request.area_unit
            ),

            expected_harvest_days=(
                request.expected_harvest_days
            ),

            growth_stage=(
                request.growth_stage
            ),

            previous_application_count=(
                request.previous_application_count
            ),

            days_since_last_application=(
                request.days_since_last_application
            ),

            state=(
                request.state
            ),

            district=(
                request.district
            ),

            latitude=(
                request.latitude
            ),

            longitude=(
                request.longitude
            ),
        )


        advisory_result = get_advisory(
            request=advisory_request,
            db=db,
        )


        # ----------------------------------------------------
        # Convert response object into dictionary
        # ----------------------------------------------------

        if hasattr(
            advisory_result,
            "model_dump",
        ):

            result_data = (
                advisory_result.model_dump()
            )

        elif isinstance(
            advisory_result,
            dict,
        ):

            result_data = (
                advisory_result
            )

        else:

            result_data = {
                "result":
                    str(advisory_result)
            }


        return {

            "execution_status":
                "completed",

            "intent":
                "advisory",

            "selected_tools":
                plan["selected_tools"],

            "missing_context":
                [],

            "decision":
                result_data.get(
                    "status"
                ),

            "agent_plan":
                plan,

            "result":
                result_data,
        }


    # ========================================================
    # STEP 4 â€” WEATHER SPECIALIST
    # ========================================================

    if plan["intent"] == "weather":

        specialist_result = (
            execute_specialist(

                intent="weather",

                question=(
                    request.question
                ),

                crop=(
                    plan["entities"].get(
                        "crop"
                    )
                    or request.crop
                ),

                state=(
                    request.state
                ),

                district=(
                    request.district
                ),

                latitude=(
                    request.latitude
                ),

                longitude=(
                    request.longitude
                ),
            )
        )


        return {

            "execution_status":
                specialist_result.get(
                    "status"
                ),

            "intent":
                "weather",

            "selected_tools":
                plan["selected_tools"],

            "missing_context":
                [],

            "agent_plan":
                plan,

            "result":
                specialist_result,
        }


    # ========================================================
    # STEP 5 â€” SOIL SPECIALIST
    # ========================================================

    if plan["intent"] == "soil":

        specialist_result = (
            execute_specialist(

                intent="soil",

                question=(
                    request.question
                ),

                crop=(
                    plan["entities"].get(
                        "crop"
                    )
                    or request.crop
                ),

                state=(
                    request.state
                ),

                district=(
                    request.district
                ),

                latitude=(
                    request.latitude
                ),

                longitude=(
                    request.longitude
                ),
            )
        )


        return {

            "execution_status":
                specialist_result.get(
                    "status"
                ),

            "intent":
                "soil",

            "selected_tools":
                plan["selected_tools"],

            "missing_context":
                [],

            "agent_plan":
                plan,

            "result":
                specialist_result,
        }


    # ========================================================
    # STEP 6 â€” VERIFIED KNOWLEDGE / RAG SPECIALIST
    # ========================================================

    if plan["intent"] == "knowledge":

        specialist_result = (
            execute_specialist(

                intent="knowledge",

                question=(
                    request.question
                ),

                crop=(
                    plan["entities"].get(
                        "crop"
                    )
                    or request.crop
                ),

                state=(
                    request.state
                ),

                district=(
                    request.district
                ),

                latitude=(
                    request.latitude
                ),

                longitude=(
                    request.longitude
                ),
            )
        )


        return {

            "execution_status":
                specialist_result.get(
                    "status"
                ),

            "intent":
                "knowledge",

            "selected_tools":
                plan["selected_tools"],

            "missing_context":
                [],

            "agent_plan":
                plan,

            "result":
                specialist_result,
        }


    # ========================================================
    # STEP 7 â€” TREATMENT / RESISTANCE
    # ========================================================

    if plan["intent"] == "treatment_resistance":

        return {

            "execution_status":
                "planned",

            "intent":
                "treatment_resistance",

            "selected_tools":
                plan["selected_tools"],

            "missing_context":
                [],

            "message": (
                "Treatment-history and resistance "
                "specialist execution will be connected "
                "in the next step."
            ),

            "agent_plan":
                plan,

            "result":
                None,
        }


    # ========================================================
    # STEP 8 â€” FALLBACK
    # ========================================================

    return {

        "execution_status":
            "unsupported_intent",

        "intent":
            plan["intent"],

        "selected_tools":
            plan["selected_tools"],

        "missing_context":
            plan["missing_context"],

        "message": (
            "No specialist executor is currently "
            "available for this intent."
        ),

        "agent_plan":
            plan,

        "result":
            None,
    }
