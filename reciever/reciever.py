import os
import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# 1. Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'metrics.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. The ORM Model
class MetricRecord(db.Model):
    __tablename__ = 'metrics'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float)  # Adjust to db.String if sending non-numeric data
    collector_type = db.Column(db.String(50))
    unit = db.Column(db.String(20))
    timestamp = db.Column(db.String(50))
    received_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# 3. The API Route (strict_slashes=False fixes the 404 error)
@app.route('/api/metrics', methods=['POST'], strict_slashes=False)
def handle_batch():
    auth = request.authorization
    # Simple check (match these to your local .env)
    if not auth or auth.username != "your_user" or auth.password != "your_pass":
        return jsonify({"message": "Unauthorized"}), 401

    payload = request.get_json()
    if not payload or 'metrics' not in payload:
        return jsonify({"error": "No metrics found"}), 400

    try:
        new_entries = []
        for m in payload['metrics']:
            entry = MetricRecord(
                name=m['name'],
                value=m['value'],
                collector_type=m['collector_type'],
                unit=m['unit'],
                timestamp=m['timestamp']
            )
            new_entries.append(entry)
        
        db.session.add_all(new_entries)
        db.session.commit()
        return jsonify({"status": "success", "count": len(new_entries)}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 4. Initialize Database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    # Setting host to 0.0.0.0 allows the tunnel to connect properly
    app.run(debug=True, host='0.0.0.0', port=5000)