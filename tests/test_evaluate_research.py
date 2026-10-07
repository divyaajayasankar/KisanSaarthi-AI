"""The research evaluator must score the real engine at 100% on a known fixture,
and it must register failures when the engine or a baseline is wrong."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models_conversation  # noqa: F401
import app.models_crop_soil  # noqa: F401
import app.models_resistance  # noqa: F401
import app.models_trace  # noqa: F401
from app.db import Base
from app.models import RegistryEntry
from app.models_growth_stage import GrowthStageRule
from app.models_treatment_history import TreatmentHistoryRule
from scripts import evaluate_research as er


def _registry(crop, pest, ai, dose, unit, phi, na=False):
    return RegistryEntry(
        crop=crop, pest=pest, active_ingredient=ai, formulation="FIXTURE",
        dose_min_per_hectare=dose, dose_max_per_hectare=dose, dose_unit=unit, phi_days=phi,
        phi_not_applicable=na, source_document="FIXTURE", source_page=1,
        source_url="https://example.org/fixture", verified=True, is_test_data=False,
    )


@pytest.fixture()
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with maker() as db:
        db.add_all([
            _registry("Rice", "Blast; Sheath blight", "Tricyclazole", 300, "g", 14),
            _registry("Banana", "Sigatoka", "Propiconazole", 500, "ml", 0, na=True),
            GrowthStageRule(crop="Rice", pest="Blast; Sheath blight", active_ingredient="Tricyclazole",
                            allowed_stages="vegetative;reproductive", application_timing="fixture",
                            source_document="FIXTURE", source_page=1, source_url="https://example.org/f", source_date="2020-01-01", verified=True),
            TreatmentHistoryRule(crop="Rice", pest="Blast; Sheath blight", active_ingredient="Tricyclazole",
                                 max_applications=3, min_interval_days=14, history_scope="season",
                                 application_stage=None, verified=True, source_document="FIXTURE",
                                 source_page=1, source_url="https://example.org/f", notes="fixture"),
        ])
        db.commit()
    return maker


def test_grid_scores_engine_perfectly_and_baselines_fail(factory):
    with factory() as db:
        grid = er.run_grid(db)
    m = grid["metrics"]
    assert grid["scenarios"] > 100
    p = m["proposed"]
    assert p["safety_violations"] == 0 and p["safety_compliance_rate"] == 1.0
    assert p["decision_accuracy_3class"] == 1.0
    assert p["dose_accuracy"] == 1.0 and p["phi_compliance"] == 1.0
    assert p["abstention_precision"] == 1.0 and p["abstention_recall"] == 1.0
    assert grid["grounding"]["rate"] == 1.0
    # simulated baselines ignore context, so they must violate safety
    assert m["B2_registry_only_simulated"]["safety_violations"] > 0
    assert m["B3_calculator_simulated"]["safety_violations"] > 0
    assert m["B2_registry_only_simulated"]["dose_accuracy"] < 1.0
    # every ablation of a safety source must show violations, ablating area must hurt dose accuracy
    for name in ("abl_no_weather", "abl_no_phi", "abl_no_history", "abl_no_stage", "abl_no_abstention_simulated"):
        assert m[name]["safety_violations"] > 0, name
    assert m["abl_no_area"]["dose_accuracy"] < 1.0
    assert grid["b1_direct_llm"]["status"].startswith("NOT RUN")


def test_oracle_and_engine_disagreement_is_detected(factory, monkeypatch):
    import app.routers.advisory as advisory

    real = advisory.evaluate_weather_safety
    monkeypatch.setattr(advisory, "evaluate_weather_safety",
                        lambda weather: type(real(weather))(status="proceed", explanation="forced", fired_rules=[]))
    with factory() as db:
        grid = er.run_grid(db)
    assert grid["metrics"]["proposed"]["safety_violations"] > 0
    assert grid["metrics"]["proposed"]["safety_compliance_rate"] < 1.0


def test_b1_direct_llm_runs_with_a_stub_and_is_scored(factory):
    calls = []

    def always_recommend(prompt):
        calls.append(prompt)
        return 'Sure. {"decision": "recommend", "dose": 100, "unit": "g"}'

    with factory() as db:
        grid = er.run_grid(db, b1_sample=12, ask=always_recommend)
    b1 = grid["b1_direct_llm"]
    assert len(calls) == 12 and b1["status"] == "run" and b1["answered"] == 12
    assert b1["safety_violations"] >= 0 and b1["dose_accuracy"] is not None


def test_unparsable_llm_answers_are_not_counted(factory):
    with factory() as db:
        grid = er.run_grid(db, b1_sample=5, ask=lambda p: "I cannot answer")
    assert grid["b1_direct_llm"]["status"] == "run but no parsable answers"


def test_tool_arguments_are_scored_per_field_and_language():
    result = er.tool_argument_accuracy()
    assert result["utterances"] == len(er.GOLD)
    assert set(result["by_language"]) == {"en", "hi", "ta", "te"}
    assert result["exact_match_rate"] is not None
    assert result["field_accuracy"]["land_unit"] is not None


def test_chat_checks_on_fixture(factory):
    chat = er.chat_checks(factory)
    assert chat["status"] == "run", chat
    assert chat["irrelevant_context_stability"]["rate"] is not None
    assert chat["multilingual_consistency"]["detail"]["en"]["same_as_english"] is True
    assert chat["ablation_no_memory"]["reaches_answer"] is False
    assert chat["ablation_no_retrieval"]["same_decision_and_dose"] is True
    assert chat["latency_chat_turn"]["n"] > 10


def test_chat_checks_say_not_run_when_reference_case_cannot_answer():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    chat = er.chat_checks(sessionmaker(bind=engine))
    assert chat["status"].startswith("NOT RUN")


def test_retrieval_not_run_without_knowledge_base(tmp_path):
    assert er.retrieval_hit_at_k(tmp_path / "missing.json")["status"].startswith("NOT RUN")


def test_retrieval_scores_a_small_knowledge_base(tmp_path):
    kb = tmp_path / "kb.json"
    kb.write_text(json.dumps([
        {"id": "r1", "crop": "Rice", "topic": "rice blast leaf lesions", "text": "Blast shows spindle lesions on rice leaves.",
         "category": "symptom", "verified": True},
        {"id": "r2", "crop": "Rice", "topic": "rice sheath blight rot", "text": "Sheath blight rots the lower rice sheath.",
         "category": "symptom", "verified": True},
    ]), encoding="utf-8")
    result = er.retrieval_hit_at_k(kb)
    assert result["status"] == "run" and result["queries"] == 2
    assert result["hit@5"] is not None


def test_reports_are_written_and_have_limits(factory, tmp_path):
    result = er.run_all(factory, knowledge_base_path=tmp_path / "missing.json")
    er.write_reports(result, tmp_path)
    md = (tmp_path / "research_eval.md").read_text(encoding="utf-8")
    assert "Limits" in md and "B2 and B3 are simulated" in md and "NOT RUN" in md
    assert (tmp_path / "research_eval.csv").exists()
    assert json.loads((tmp_path / "research_eval.json").read_text(encoding="utf-8"))["grid"]["scenarios"] > 0


def test_chat_checks_make_no_network_calls_even_with_a_key_configured(factory, monkeypatch):
    from types import SimpleNamespace

    from app.services import location_service, soilgrids_rootzone, weather_service

    def forbidden(*args, **kwargs):
        raise AssertionError("network call attempted during evaluation")

    class _Never(Exception):
        pass

    blocked = SimpleNamespace(Client=forbidden, HTTPError=_Never, RequestError=_Never, HTTPStatusError=_Never)
    monkeypatch.setattr(weather_service, "OPENWEATHER_API_KEY", "dummy-key")
    monkeypatch.setattr(location_service, "httpx", blocked)
    monkeypatch.setattr(weather_service, "httpx", blocked)
    chat = er.chat_checks(factory)
    assert chat["status"] == "run", chat
    assert weather_service.OPENWEATHER_API_KEY == "dummy-key"  # restored afterwards


def test_per_key_cap_samples_deterministically_and_reports_it(factory, tmp_path):
    lines = []
    with factory() as db:
        a = er.run_grid(db, per_key_cap=20, progress=lines.append)
    with factory() as db:
        b = er.run_grid(db, per_key_cap=20)
    assert a["scenarios"] <= 40 and a["scenarios"] < a["scenarios_full_grid"] and a["scenarios_sampled"] == a["scenarios"]
    assert [d["pass"] for d in a["detail"]] == [d["pass"] for d in b["detail"]]
    assert any("grid 2/2" in line for line in lines)
    result = {"grid": a, "tool_arguments": er.tool_argument_accuracy(), "chat": {"status": "n/a"}, "retrieval": {"status": "NOT RUN"}}
    assert "at most 20 per key" in er.render_markdown(result)
