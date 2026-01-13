# api/index.py
from flask import Flask, jsonify
from app import app as flask_app

# Vercel requires a function named `handler` for serverless deployment
def handler(request):
    return flask_app(request.environ, start_response)

# This is to make it easier to test locally with `python api/index.py`
if __name__ == '__main__':
    flask_app.run(debug=True, port=5000)
