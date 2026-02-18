from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
import os

load_dotenv()

HOST = os.getenv('HOST')
PORT = os.getenv('PORT')

app = Flask(__name__)

if __name__ == "__main__":
    app.run(debug=True, host=HOST, port=PORT)



