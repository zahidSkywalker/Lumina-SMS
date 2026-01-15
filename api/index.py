# api/index.py
from app import app as flask_app

# This is the Vercel entry point
def handler(event, context):
    # Vercel passes the event/context. We pass them to Flask.
    # We provide a dummy 'start_response' to satisfy WSGI interface
    return flask_app(event.environ, lambda status, headers: None)

# This is to make it easier to test locally with `python api/index.py`
if __name__ == '__main__':
    flask_app.run(debug=True, port=5000)
