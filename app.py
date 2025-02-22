from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import firebase_admin
from firebase_admin import credentials, db
import cloudinary
import cloudinary.uploader
import time
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Firebase
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://gauri-33b54-default-rtdb.firebaseio.com/'
})

# Initialize Firebase references
messages_ref = db.reference("messages")
notes_ref = db.reference("notes")

# Cloudinary Setup
cloudinary.config(
    cloud_name="dejlyocyq",
    api_key="612143172989225",
    api_secret="ujJYvD61LKUHB5ivKHrBeckRg54",
    secure=True
)

@app.route('/')
def index():
    return render_template('index.html')

# Note handling
@app.route('/api/notes', methods=['GET', 'POST'])
def handle_notes():
    if request.method == 'POST':
        data = request.json
        note = {
            "content": data["content"],
            "timestamp": time.time(),
            "pinned": data.get("pinned", False)
        }
        notes_ref.push(note)
        return jsonify({"status": "success"})
    else:
        notes = notes_ref.get()
        return jsonify(notes if notes else {})

@app.route('/api/notes/<note_id>', methods=['PUT', 'DELETE'])
def handle_note(note_id):
    if request.method == 'PUT':
        data = request.json
        notes_ref.child(note_id).update(data)
        return jsonify({"status": "success"})
    else:
        notes_ref.child(note_id).delete()
        return jsonify({"status": "success"})

# Socket.IO chat events
@socketio.on('send_message')
def handle_send_message(data):
    message = {
        "content": data["message"],
        "timestamp": time.time(),
        "type": "text"
    }
    message_id = messages_ref.push(message).key
    message["id"] = message_id
    emit('receive_message', message, broadcast=True)

@socketio.on('send_file')
def handle_send_file(data):
    if "file" in data:
        try:
            result = cloudinary.uploader.upload(data["file"])
            message = {
                "content": f"📎 Shared a file: [Download]({result['secure_url']})",
                "timestamp": time.time(),
                "type": "file",
                "file_url": result['secure_url']
            }
            message_id = messages_ref.push(message).key
            message["id"] = message_id
            emit('receive_message', message, broadcast=True)
        except Exception as e:
            emit('error', {"message": "File upload failed"})
    else:
        emit('error', {"message": "No file provided"})

@socketio.on('connect')
def handle_connect():
    # Send existing messages
    messages = messages_ref.get()
    if messages:
        for msg_id, msg in messages.items():
            msg["id"] = msg_id
            emit('receive_message', msg)
    
    # Send existing notes
    notes = notes_ref.get()
    if notes:
        for note_id, note in notes.items():
            note["id"] = note_id
            emit('receive_note', note)
@socketio.on('clear_chat')
def handle_clear_chat():
    # Delete all messages from the Firebase "messages" reference
    messages_ref.delete()
    # Broadcast a clear_chat event to all connected clients
    emit('clear_chat', broadcast=True)

if __name__ == '__main__':
    os.environ.get("PORT", 5000)
    socketio.run(app, debug=True, host="0.0.0.0", port=port)
