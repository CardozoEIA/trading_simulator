"""Print the similarity of the best chunks for a list of questions, to choose the thresholds.

Usage (from backend/, with Ollama running and some documents uploaded):
    python -m scripts.calibrate_threshold <user_id>

Edit IN_SCOPE / OUT_OF_SCOPE below with questions about YOUR documents and questions that are
clearly unrelated. Then pick MIN_BEST_SIMILARITY between the two groups.
"""
import sys

from app.vectorstore.embeddings import embed_query
from app.vectorstore.repository import search_chunks

IN_SCOPE = [
    "What does the Sharpe ratio measure?",
    "How does a stop-loss work?",
    "What is maximum drawdown?",
    "When is the RSI considered overbought?",
    "What is look-ahead bias?",
    "What does the win rate tell me?",
    # Spanish and reworded versions of the same topics
    "¿Qué mide el ratio de Sharpe?",
    "Explain RSI like I'm five",
    "¿Qué es un stop-loss?",
    "¿Qué es el drawdown máximo?",
    "What does an RSI above 70 mean?",
    "Why shouldn't a simulation peek at future prices?",
]
OUT_OF_SCOPE = [
    "What is the best recipe for sushi?",
    "Who won the 2018 football world cup?",
    "How do I change a car tire?",
    "How do I buy Bitcoin?",
    "What will Tesla stock do next week?",
    "What is the capital of France?",
    "How much money did Apple make last year?",
    "¿Cuál es la receta del arroz con pollo?",
    "¿Quién ganó el último mundial de fútbol?",
    "What is a P/E ratio?",
]


def best_similarity(user_id: str, question: str) -> float:
    rows = search_chunks(embed_query(question), user_id, threshold=0.0, top_k=1)
    return rows[0]["similarity"] if rows else 0.0


if __name__ == "__main__":
    user = sys.argv[1]

    for title, questions in (("SHOULD be answered", IN_SCOPE), ("should be REFUSED", OUT_OF_SCOPE)):
        print(f"\n{title}")
        for q in questions:
            print(f"  {best_similarity(user, q):.3f}  {q}")
