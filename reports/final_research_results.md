# KisanSaarthi AI — Final Research Results

## Project Title

A Context-Aware Agentic AI for Personalized Crop Advisory for Indian Farmers


## 1. Research Objective

The objective of this work is to evaluate whether a crop advisory system
responds correctly to decision-relevant changes in farmer context while
remaining stable when irrelevant context changes.

The system integrates:

- Verified crop-pest registry evidence
- Field-area-based dose scaling
- Pre-harvest interval verification
- Crop growth-stage validation
- Previous treatment history
- Resistance and mode-of-action information
- Weather context
- Soil context
- Verified agricultural RAG
- Agentic intent detection and specialist tool selection


## 2. Decision Framework

The advisory system produces one of three safety-oriented decisions:

- RECOMMEND
- DELAY
- ABSTAIN

Safety-critical decisions are produced using deterministic,
evidence-grounded rules rather than generating pesticide dose or
harvest-safety information from model memory.


## 3. Context Sensitivity Evaluation

The controlled context-sensitivity experiment evaluated six
decision-relevant context pairs.

### Relevant Context Cases

1. PHI / harvest horizon
2. Crop growth stage
3. Previous treatment count
4. Repeat-treatment interval
5. Weather / wind condition
6. Field-area dose scaling

All six relevant-context cases produced the expected context-sensitive
change.

### Context Sensitivity Score

CSS = 6 / 6 = 100.00%


## 4. Irrelevant Context Stability

Two controlled irrelevant-context tests were evaluated:

1. Capitalization and whitespace variation
2. Repeat-day variation when no verified repeat interval applies

Both cases remained stable.

ICS = 2 / 2 = 100.00%


## 5. Final Controlled Evaluation Metrics

| Metric | Result |
|---|---:|
| Context Sensitivity Score | 100.00% |
| Irrelevant Context Stability | 100.00% |
| Decision Accuracy | 100.00% |
| Safety Violation Rate | 0.00% |
| Abstention Accuracy | 100.00% |
| Tool Selection Accuracy | 100.00% |


## 6. Agentic Tool Selection

The orchestration layer successfully distinguished between different
farmer-query intents.

Examples:

- Weather query -> Weather specialist
- Soil query -> Soil specialist
- Crop-management query -> Verified RAG and registry
- Spray decision -> Full advisory pipeline

The controlled tool-selection experiment achieved 100.00% accuracy
on the predefined test cases.


## 7. Ablation Study

An input-context ablation experiment was conducted by suppressing one
decision-relevant context dimension at a time while keeping the
underlying deterministic advisory engine unchanged.

| Configuration | CSS | Drop from Full System |
|---|---:|---:|
| Full system | 100.00% | 0.00 pp |
| Without PHI context | 83.33% | 16.67 pp |
| Without growth stage | 83.33% | 16.67 pp |
| Without treatment history | 66.67% | 33.33 pp |
| Without weather | 83.33% | 16.67 pp |
| Without field area | 83.33% | 16.67 pp |

The treatment-history ablation produced the largest decrease in this
evaluation because two of the six context-sensitivity cases depend on
treatment-history information.

The experiment demonstrates that context-sensitive behavior is not
produced by a single feature alone. Removing individual farmer-context
signals reduces the system's ability to respond appropriately to
context changes.


## 8. Main Research Contribution

The main contribution of KisanSaarthi AI is not merely the use of a
chatbot, RAG, weather API, soil API, or agentic architecture.

The contribution is the explicit and machine-checkable evaluation of
personalization.

The proposed framework tests whether:

1. advisory output changes when decision-relevant farmer context changes,
2. the corresponding verified rule is responsible for that change, and
3. the output remains stable under irrelevant context changes.

This makes personalization quantitatively measurable rather than only
claiming that the system is personalized.


## 9. Safety Contribution

The framework follows an evidence-first design.

If verified evidence or required context is unavailable, the system can
withhold an actionable recommendation instead of guessing.

Unsafe conditions can therefore produce:

- DELAY for temporarily unsuitable conditions such as weather, or
- ABSTAIN when verified evidence or safety requirements are insufficient.


## 10. Interpretation of Results

The controlled evaluation produced perfect scores on the predefined
test suite.

These results should not be interpreted as 100% real-world agronomic
accuracy.

They indicate that the implemented decision logic behaved correctly
for the defined and reproducible experimental scenarios.

The evaluation currently contains:

- 6 relevant-context pairs
- 2 irrelevant-context pairs
- a controlled decision test set
- a controlled tool-selection test set

Therefore, the findings demonstrate functional correctness of the
proposed context-aware mechanism within the evaluated scope rather
than universal agricultural performance.


## 11. Limitations

The current prototype has several limitations:

1. The verified registry covers a limited research subset of crops and
   crop-problem combinations.

2. Context-sensitivity evaluation currently uses a relatively small
   controlled test suite.

3. Weather is mocked during research evaluation to guarantee
   reproducibility, although the application itself can use live
   weather data.

4. Soil suitability depends on the available SoilGrids information and
   crop-specific verified rules.

5. The system does not establish universal agronomic correctness for
   every crop, region, product, or field condition.

6. Additional large-scale evaluation would be required before
   production agricultural deployment.


## 12. Conclusion

KisanSaarthi AI demonstrates a context-aware agentic crop advisory
framework in which farmer context directly participates in auditable
decision rules.

The full system achieved 100% Context Sensitivity Score and 100%
Irrelevant Context Stability on the predefined controlled evaluation
suite, with zero observed safety violations in those test cases.

Ablation experiments reduced context sensitivity when PHI,
growth-stage, treatment-history, weather, or field-area context was
suppressed, providing evidence that these personalization dimensions
contribute directly to the system's behavior.

The results support the feasibility of quantitatively evaluating
context-aware personalization in an evidence-grounded agricultural
advisory system.