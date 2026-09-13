# Verify FinBERT loads and returns sane sentiment (downloads ~440MB on first run).
from transformers import pipeline
clf = pipeline("text-classification", model="ProsusAI/finbert")
tests = [
    "The company reported record revenue growth and raised full-year guidance.",
    "The firm warned of mounting losses, liquidity concerns, and executive departures.",
    "Quarterly results were in line with expectations.",
]
for t in tests:
    r = clf(t)[0]
    print(f"{r['label']:>8} ({r['score']:.2f})  <-  {t[:60]}")
