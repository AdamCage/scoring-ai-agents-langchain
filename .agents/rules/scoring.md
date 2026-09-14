# Scoring

- Train a real CatBoostClassifier on synthetic defaults. No `random()` scores.
- Feature schema is `models/feature_schema.json`.
- SHAP values come from CatBoost ShapValues (or TreeExplainer). Positive SHAP increases PD.
- What-if reuses the same scoring and SHAP tools. No LLM on the numeric path.
- LLM explanations may only quote actual SHAP features.
