import logging
import os
from dotenv import load_dotenv

load_dotenv()

from dashboard import create_dashboard
from flask import Flask
from config.config import setup_logging
from control_ws import hub
from routes import bp
setup_logging()
logger = logging.getLogger(__name__)

HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", 5000)

app = Flask(__name__)
app.register_blueprint(bp)
create_dashboard(app)
hub.start()

if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=HOST,
        port=int(PORT),
    )
