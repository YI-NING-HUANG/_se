from flask import Flask, request, jsonify
from flask_cors import CORS
import platform
import sys
import math
import datetime

app = Flask(__name__)
CORS(app)

@app.route('/api/health')
def health():
    return jsonify({"service": "python", "status": "ok", "time": datetime.datetime.utcnow().isoformat()})

@app.route('/api/info')
def info():
    return jsonify({
        "service": "python",
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown"
    })

@app.route('/api/compute', methods=['POST'])
def compute():
    data = request.get_json(force=True, silent=True) or {}
    n = int(data.get('n', 10))
    if n < 0 or n > 1000:
        return jsonify({"error": "n must be 0..1000"}), 400
    # factorial + fibonacci demo
    fact = math.factorial(min(n, 100))
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return jsonify({"service": "python", "n": n, "factorial": str(fact), "fibonacci": a})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
