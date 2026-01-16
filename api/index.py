from app import app as flask_app

# Vercel Serverless Handler
def handler(event, context):
    # Properly handle the WSGI interface
    return flask_app(event.environ, lambda status, headers: None)

# This is to make it easier to test locally with `python api/index.py`
if __name__ == '__main__':
    flask_app.run(debug=True, port=5000)
