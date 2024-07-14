from flask import Flask, json, render_template
from werkzeug.exceptions import HTTPException
from imaginate_api.date.routes import bp as date_routes
from imaginate_api.image.routes import bp as image_routes
from imaginate_api.config import Config

# Constants
from schemas.image_info import ImageStatus


def create_app():
  app = Flask(__name__)
  app.config.from_object(Config)
  app.register_blueprint(date_routes, url_prefix="/date")
  app.register_blueprint(image_routes, url_prefix="/image")
  return app


# Create app
app = create_app()


# This endpoint is simply for testing purposes
@app.route("/")
def index():
  return render_template("index.html")


# Generic error handler in JSON rather than HTML
@app.errorhandler(HTTPException)
def handle_exception(exc: HTTPException):
  response = exc.get_response()
  response.data = json.dumps(
    {
      "code": exc.code,
      "name": exc.name,
      "description": exc.description,
    }
  )
  response.content_type = "application/json"
  return response


# Run app on invocation
if __name__ == "__main__":
  app.run()
