# C:\farmer\tests\test_agent_execution.py

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(
    app
)


def test_agent_execute_missing_context():

    response = client.post(

        "/api/agent/execute",

        json={
            "question":
                "Can I spray for banana Sigatoka today?",

            "crop":
                "Banana",

            "pest":
                "Sigatoka",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["execution_status"]
        ==
        "needs_context"
    )

    assert (
        data["intent"]
        ==
        "advisory"
    )

    assert (
        "field_area"
        in data["missing_context"]
    )

    assert (
        "state"
        in data["missing_context"]
    )

    assert (
        "district"
        in data["missing_context"]
    )


def test_agent_query_endpoint_still_works():

    response = client.post(

        "/api/agent/query",

        json={
            "question":
                "Will it rain today?"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["intent"]
        ==
        "weather"
    )

    assert (
        data["selected_tools"]
        ==
        ["weather"]
    )
