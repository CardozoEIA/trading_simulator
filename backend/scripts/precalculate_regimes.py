"""US-23: precalculate the market-regime labels of an asset (walk-forward) and store them in Supabase.

Usage (from backend/):
    python -m scripts.precalculate_regimes            # SP500, whole history
    python -m scripts.precalculate_regimes SP500

Run it again whenever historical_data grows. Labels of the same asset + date + algorithm version are replaced.
"""
import sys
from collections import Counter
from datetime import date

from app.modules.regime.service import load_full_history, save_regime_labels
from app.services.regime.classifier import CHECKPOINT_EVERY, FIRST_CHECKPOINT_INDEX, build_regime_labels


def main(asset: str) -> None:
    candles = load_full_history(asset, date.today())
    labels = build_regime_labels(candles)
    if not labels:
        print(f"Not enough history for {asset}: {len(candles)} candles, at least {FIRST_CHECKPOINT_INDEX + 1} needed.")
        return
    written = save_regime_labels(asset, labels)
    counts = Counter(label.regime.value for label in labels)
    print(f"{asset}: {len(candles)} candles, labels from {labels[0].date} to {labels[-1].date}")
    print(f"Re-trained every {CHECKPOINT_EVERY} trading days; {written} labels saved.")
    for regime, count in counts.most_common():
        print(f"  {regime}: {count} days ({count / len(labels):.0%})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "SP500")
