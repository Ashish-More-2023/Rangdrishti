"""Rangdrishti domain logic. Pure Python: nothing in this package imports Django.

Subpackages:
    screenplay/  parse, normalise and validate screenplays  (Stage 1, done)
    candidates/  rule-based promo candidates                (Stage 2, done)
    validation/  hard rules every promo must pass           (Stage 2, done)
    evaluation/  gold-set recall vs a random baseline       (Stage 2, done)
    judge/       AI judging, final ranking, exports         (Stage 3, done)
    ai/          swappable providers (Gemini/OpenAI-compatible, mock)
"""
