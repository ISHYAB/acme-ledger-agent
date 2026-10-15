
from flask import Flask, request, jsonify
from query_engine import answer_question

app = Flask(__name__)


@app.route("/", methods=["POST"])
def answer():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "A non-empty question is required"}), 400

    try:
        result = answer_question(question)
        return jsonify({"answer": result}), 200
    except Exception:
        app.logger.exception("Failed to answer question")
        return jsonify({"error": "Unable to process the question"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
