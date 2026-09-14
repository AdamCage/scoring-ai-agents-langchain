# What-if и чат

What-if (`POST /api/what-if`) пересчитывает CatBoost и SHAP на копии заявки. LLM не участвует в числах.

Чат (`POST /api/chat`) отвечает по сохранённому state run: score, SHAP, цитаты. Это subgraph после human review, а не новый скоринг.

![What-if](../screenshots/ui/whatif.png)
