from flask import Flask, request, jsonify, redirect, render_template_string
from flask_cors import CORS
import json
import os
from datetime import datetime
import validators

app = Flask(__name__)
CORS(app)

# File to store QR mappings (in production, use a proper database)
DATA_FILE = 'qr_mappings.json'

def initialize_data_file():
    """Initialize the data file if it doesn't exist"""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w') as f:
            json.dump({}, f)

def read_mappings():
    """Read QR mappings from file"""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def write_mappings(mappings):
    """Write QR mappings to file"""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(mappings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing mappings: {e}")
        return False

def log_access(qr_id, destination, user_agent, ip):
    """Log QR code access for analytics"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'qr_id': qr_id,
        'destination': destination,
        'user_agent': user_agent,
        'ip': ip
    }
    
    log_file = 'qr_access.log'
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"Error logging access: {e}")

# Initialize data file on startup
initialize_data_file()

# ROUTES

@app.route('/')
def home():
    """API documentation and status"""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dynamic QR Redirect Server</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-left: 4px solid #007bff; }
            .method { font-weight: bold; color: #007bff; }
            .status { background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔗 Dynamic QR Redirect Server</h1>
            <div class="status">✅ Server is running on port {{ port }}</div>
            
            <h2>📋 Available Endpoints</h2>
            
            <div class="endpoint">
                <div class="method">GET /redirect/&lt;qr_id&gt;</div>
                <div>Redirect to destination URL for QR ID (this is what your QR codes point to)</div>
            </div>
            
            <div class="endpoint">
                <div class="method">POST /api/update</div>
                <div>Update destination URL for QR ID</div>
                <div><strong>Body:</strong> {"qr_id": "your_id", "destination_url": "https://example.com"}</div>
            </div>
            
            <div class="endpoint">
                <div class="method">GET /api/mapping/&lt;qr_id&gt;</div>
                <div>Get current destination for specific QR ID</div>
            </div>
            
            <div class="endpoint">
                <div class="method">GET /api/mappings</div>
                <div>Get all QR mappings and statistics</div>
            </div>
            
            <div class="endpoint">
                <div class="method">DELETE /api/mapping/&lt;qr_id&gt;</div>
                <div>Delete QR mapping</div>
            </div>
            
            <div class="endpoint">
                <div class="method">GET /api/stats/&lt;qr_id&gt;</div>
                <div>Get access statistics for QR ID</div>
            </div>
            
            <h2>📱 Flutter App Configuration</h2>
            <p>Update your Flutter app's <code>_redirectBaseUrl</code> to:</p>
            <div style="background: #f8f9fa; padding: 10px; font-family: monospace; border-radius: 5px;">
                http://localhost:{{ port }}/redirect/
            </div>
            
            <h2>🎯 Example QR Code URL</h2>
            <div style="background: #f8f9fa; padding: 10px; font-family: monospace; border-radius: 5px;">
                http://localhost:{{ port }}/redirect/qr123
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template, port=request.environ.get('SERVER_PORT', '5000'))

@app.route('/redirect/<qr_id>')
def redirect_qr(qr_id):
    """Main redirect endpoint - this is what the QR code points to"""
    mappings = read_mappings()
    
    if qr_id not in mappings:
        return jsonify({
            'error': 'QR code not found',
            'qr_id': qr_id,
            'message': 'This QR code has not been configured yet.'
        }), 404
    
    destination = mappings[qr_id]['destination_url']
    
    # Log the access
    user_agent = request.headers.get('User-Agent', 'Unknown')
    ip = request.remote_addr
    log_access(qr_id, destination, user_agent, ip)
    
    # Update access count
    mappings[qr_id]['access_count'] = mappings[qr_id].get('access_count', 0) + 1
    mappings[qr_id]['last_accessed'] = datetime.now().isoformat()
    write_mappings(mappings)
    
    return redirect(destination, code=302)

@app.route('/api/update', methods=['POST'])
def update_mapping():
    """Update destination URL for a QR ID"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        qr_id = data.get('qr_id')
        destination_url = data.get('destination_url')
        
        if not qr_id or not destination_url:
            return jsonify({
                'error': 'Missing required fields',
                'required': ['qr_id', 'destination_url']
            }), 400
        
        # Validate URL
        if not validators.url(destination_url):
            return jsonify({'error': 'Invalid URL format'}), 400
        
        mappings = read_mappings()
        
        # Create or update mapping
        if qr_id not in mappings:
            mappings[qr_id] = {
                'destination_url': destination_url,
                'created_at': datetime.now().isoformat(),
                'access_count': 0
            }
        else:
            mappings[qr_id]['destination_url'] = destination_url
            mappings[qr_id]['updated_at'] = datetime.now().isoformat()
        
        if write_mappings(mappings):
            return jsonify({
                'success': True,
                'message': f'QR mapping updated successfully',
                'qr_id': qr_id,
                'destination_url': destination_url
            })
        else:
            return jsonify({'error': 'Failed to save mapping'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mapping/<qr_id>')
def get_mapping(qr_id):
    """Get current destination for specific QR ID"""
    mappings = read_mappings()
    
    if qr_id not in mappings:
        return jsonify({'error': 'QR ID not found'}), 404
    
    return jsonify({
        'qr_id': qr_id,
        'mapping': mappings[qr_id]
    })

@app.route('/api/mappings')
def get_all_mappings():
    """Get all QR mappings"""
    mappings = read_mappings()
    return jsonify({
        'total_qr_codes': len(mappings),
        'mappings': mappings
    })

@app.route('/api/mapping/<qr_id>', methods=['DELETE'])
def delete_mapping(qr_id):
    """Delete QR mapping"""
    mappings = read_mappings()
    
    if qr_id not in mappings:
        return jsonify({'error': 'QR ID not found'}), 404
    
    del mappings[qr_id]
    
    if write_mappings(mappings):
        return jsonify({
            'success': True,
            'message': f'QR mapping for {qr_id} deleted successfully'
        })
    else:
        return jsonify({'error': 'Failed to delete mapping'}), 500

@app.route('/api/stats/<qr_id>')
def get_stats(qr_id):
    """Get access statistics for QR ID"""
    mappings = read_mappings()
    
    if qr_id not in mappings:
        return jsonify({'error': 'QR ID not found'}), 404
    
    mapping = mappings[qr_id]
    
    return jsonify({
        'qr_id': qr_id,
        'destination_url': mapping['destination_url'],
        'access_count': mapping.get('access_count', 0),
        'created_at': mapping.get('created_at'),
        'updated_at': mapping.get('updated_at'),
        'last_accessed': mapping.get('last_accessed')
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'total_qr_codes': len(read_mappings())
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🚀 Starting Dynamic QR Redirect Server...")
    print("📋 Server will be available at: http://localhost:5000")
    print("📖 API documentation at: http://localhost:5000")
    print("🔗 Example QR URL: http://localhost:5000/redirect/qr123")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )