# KisanSaarthi AI: Context-Aware Agentic AI for Personalized Crop Advisory

M.Tech Data Science final-year project. Chat-based crop advisory for Indian
farmers over 15 crops, in English, Hindi, Tamil and Telugu, with text, voice,
image, camera and location input.

## 1. Research problem

A pesticide advisory is safe only if it fits the farmer's field: the crop and
its growth stage, the area to treat, the pest, what was already sprayed, the
days left before harvest and the weather on the day. Generic advice and
free-form LLM answers ignore these facts or invent numbers. A wrong dose or a
spray inside the pre-harvest interval (PHI) harms health, trade and yield.

## 2. Gap

- Image classifiers return a label with no spray decision attached.
- LLM chatbots produce fluent doses with no source and no refusal path.
- Existing advisory tools rarely check PHI, growth stage, repeat use of one
  mode of action, and weather together, and rarely say "I do not know".

## 3. Contribution

1. A deterministic constraint engine over a verified registry. Dose, area
   conversion, PHI, growth stage, spray interval, IRAC/FRAC rotation and
   weather are computed by code, never by a language model.
2. A decision controller that returns exactly one of ANSWER, ASK_FOLLOW_UP,
   ABSTAIN, with configurable image-confidence thresholds.
3. A multi-turn chat agent that collects missing context (crop, area, pest,
   growth stage, harvest date, last spray, location) in four languages.
4. Crop-aware image analysis. A crop with no validated model gets an image
   ABSTAIN, not an invented diagnosis.
5. A reproducible evaluation: real-field image set, calibration metrics and a
   personalization check against independent oracles.

## 4. Crops

rice, wheat, maize, tomato, chilli, brinjal, onion, potato, okra, cabbage,
groundnut, chickpea, mustard, cotton, banana.

## 5. Architecture

```
Browser chat UI (text, voice, image, camera, location)
        |
FastAPI  /api/chat/turn  /api/chat/message  /api/speech/transcribe  /api/vision/analyze
        |
Chat orchestrator (conversation state in SQLite)
   |- Language service: detect, protected translation (doses, units, dates, ingredients are locked)
   |- Context extraction: lexicon in 4 languages; optional LLM fills only missed fields
   |- Pest alias layer: farmer phrase or model label -> canonical pest -> registry row
   |- Vision inference: crop-aware MobileNetV3, temperature-scaled confidence
   |- Location service: GPS, or place name -> coordinates (OpenWeather)
   |- Decision controller: ANSWER / ASK_FOLLOW_UP / ABSTAIN
        |
Advisory pipeline -> deterministic constraint engine
   registry, dose scaling, PHI, growth stage, treatment history,
   IRAC/FRAC resistance, weather, soil
        |
SQLite (verified registry rows, rules, sessions)
```

Two operating modes:

| Mode | LLM | Use |
|---|---|---|
| B (default) | off | Fully deterministic. Template responses in 4 languages. |
| A | on | LLM may fill context fields the lexicon missed (validated against a fixed vocabulary). It never computes or overrides PHI, dose, area, interval, thresholds, weather or safety decisions. |

## 6. Chat UI

`frontend/chat/index.html`, served at `/`. Single page, no build step. Chat
bubbles, language selector, image upload, camera capture, "use my location",
microphone. The original form UI, if you import it, is served at `/classic`.

## 7. Image, camera and location

- Upload or camera image is validated (type, size, decodable) and stored under
  `data/uploads` (excluded from the ZIP).
- Location: browser GPS, or the farmer types a place ("Madurai, Tamil Nadu").
- Image evidence is used only when a validated model exists for that crop and
  the confidence passes the controller thresholds.

## 8. Multilingual text and voice

- Text: English, Hindi, Tamil, Telugu. Doses, units, dates and active
  ingredient names are replaced by markers before translation and restored
  after. A translation that loses a marker is rejected, and the untranslated
  engine text is shown instead.
- Voice: faster-whisper on CPU (`WHISPER_MODEL=small`, `int8`). Flow:
  record, transcribe, show the text, farmer confirms or edits, then send. Audio
  is never acted on directly.
- The Hindi, Tamil and Telugu message templates have not been reviewed by
  native speakers. Treat them as draft until they are.

## 9. Disease analysis

`POST /api/vision/analyze` runs the crop's own MobileNetV3 model when
`data/models/model_registry.json` lists one with `validated: true`. A model is
marked validated only if validation macro-F1 reaches `--min-macro-f1` in
`scripts/train_crop_model.py`. Output labels pass through the pest alias layer;
a label with no matching verified registry row cannot produce a recommendation.

## 10. Safety rules (all deterministic)

| Rule | Behavior |
|---|---|
| Registry | Only verified rows are used. No row, no recommendation. |
| Dose scaling | Label dose per unit area scaled to the farmer's area. Units converted by code. |
| PHI | Days to harvest must be at least the PHI, else the engine returns `delay` or `abstain`. |
| Growth stage | Product use is checked against permitted stages. Flowering and fruiting map to reproductive. |
| Treatment history | Minimum re-spray interval from verified history rules is checked. If the last spray is unknown and the same ingredient is a candidate, the agent asks once. |
| Resistance | IRAC/FRAC mode of action. Repeat use gives a rotation warning, not a fabricated ban. |
| Weather | Rain, wind, temperature thresholds. No verified weather means no advisory. |

## 11. Decision controller

| Decision | When |
|---|---|
| ANSWER | Required context present, rules pass, image evidence (if any) at or above `VISION_ANSWER_THRESHOLD` (0.80). |
| ASK_FOLLOW_UP | A needed fact is missing, or image confidence is between `VISION_ASK_THRESHOLD` (0.55) and 0.80 and the farmer must confirm. Capped by `MAX_FOLLOW_UP_TURNS`. |
| ABSTAIN | No validated crop model, confidence below 0.55, no verified registry row, PHI or weather unsafe, or follow-up limit reached. |

## 12. Evaluation

### Real-field image set

`data/real_field_eval`: 15 crops x 5 images = 75 images, with `metadata.csv`
(`crop,disease,filename,source,dataset,license`). Used for evaluation only,
never for training. `train_crop_model.py` excludes these images by SHA-256.

`scripts/build_eval_metadata.py` never guesses provenance. Unknown values are
written as `TO_VERIFY`. Images without a verified disease label are excluded
from accuracy.

`scripts/evaluate_real_field.py` reports accuracy, per-class precision,
recall and F1, macro-F1, confusion matrix, top-label Brier score, expected
calibration error (10 bins), coverage, selective accuracy and abstention
rate, per crop and overall. Only labeled images with a validated model are
scored; the rest are counted as abstentions. Outputs: `reports/real_field_eval_*`.

### Personalization evaluation

`scripts/evaluate_personalization.py` compares the pipeline against independent
oracles written separately from the engine: dose scaling, PHI, growth stage,
treatment history and synthetic weather cases. Outputs:
`reports/personalization_eval.csv` and `.md`. It needs verified registry rows.

### Tests

`pytest` covers the engine, resistance, weather, soil, growth stage, registry
coverage, alias layer, decision controller, chat orchestrator, upload and
multimodal endpoints, both evaluation scripts, and the packager.

## 13. Install

Requires Python 3.10 or newer. No admin rights.

```
.\scripts\import_local_assets.ps1 -Source C:\farmer
.\run_project.ps1
```

See `RUN_COMMANDS.txt` for every command. Copy `.env.example` to `.env`
(`run_project.ps1` does this) and set `OPENWEATHER_API_KEY`. Never commit `.env`.

Vision training and inference need `requirements-vision.txt` (torch,
torchvision). Run `.\run_project.ps1 -WithVision`.

## 14. Run

```
.\run_project.ps1
```

Chat `http://127.0.0.1:8000`, docs `/docs`, status `/api/status`.

## 15. Test

```
.\.venv\Scripts\python.exe -m pytest -q
```

## 16. Known limitations

- No crop image model is validated yet. Every image-based query abstains until
  you train and validate one per crop on data you are licensed to use.
- The 75-image evaluation set is complete only when you place it there. Its
  `source`, `dataset` and `license` fields stay `TO_VERIFY` until you confirm
  provenance. Do not report accuracy from unverified labels.
- `train_crop_model.py` picks the epoch and calibrates temperature on the same
  validation split, so its reported validation metrics are optimistic. Use the
  real-field set for the honest number.
- Real Whisper transcription was not run during development (the model
  download was blocked). The endpoint is tested with a mocked model.
- `run_project.ps1` was tested on PowerShell 7 on Linux, not on Windows
  PowerShell 5.1.
- `data/registry/pest_aliases.csv` was not checked against your verified
  registry. An alias only helps where a matching registry row exists. Run
  `python -m scripts.validate_pest_aliases`.
- Hindi, Tamil and Telugu text is unreviewed by native speakers.
- Weather and place lookup need an OpenWeather key and network access.
- The registry is only as good as its verification. Doses are label values,
  not agronomic recommendations for your field.

## 17. Future work

WhatsApp delivery is not implemented. A future bot would reuse
`/api/chat/turn` unchanged: receive text, image and location messages, call the
same endpoint, send back the reply. This needs the WhatsApp Business API,
webhook verification, and a consent and retention policy for farmer data.
Other future items: per-crop validated models, farmer-profile persistence,
native-speaker review of translations, field trials.

## 18. Data and secrets

The ZIP contains code, reference data and a sanitized database copy (reference
tables only, personal tables emptied) when a live database exists. It contains
no `.env`, no API keys, no raw datasets and no model weights outside the
registry.
