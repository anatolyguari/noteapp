from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import firebase_admin
from firebase_admin import credentials, db
import cloudinary
import cloudinary.uploader
import time
from datetime import datetime
import os
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Firebase
firebase_creds = os.environ.get("FIREBASE_CREDENTIALS")
if firebase_creds:
    # Load credentials from the environment variable (as a JSON string)
    cred_info = json.loads(firebase_creds)
    cred = credentials.Certificate(cred_info)
else:
    # Fallback to local file (ensure this file is in your .gitignore)
    cred = credentials.Certificate("firebase_credentials.json")

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://rahilshaikh-6d1f2-default-rtdb.firebaseio.com/'
})

# Firebase references
messages_ref  = db.reference("messages")
notes_ref     = db.reference("notes")
reminders_ref = db.reference("reminders")
labels_ref    = db.reference("labels")

# Cloudinary Setup (using your credentials)
cloudinary.config(
    cloud_name="dejlyocyq",
    api_key="612143172989225",
    api_secret="ujJYvD61LKUHB5ivKHrBeckRg54",
    secure=True
)

# Custom Jinja filter to format timestamps
@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M')

# Pass data to the template so items persist on refresh
@app.route('/')
def index():
    notes = notes_ref.get() or {}
    reminders = reminders_ref.get() or {}
    labels = labels_ref.get() or {}
    return render_template('index.html', notes=notes, reminders=reminders, labels=labels)

# NOTES ENDPOINTS
@app.route('/api/notes', methods=['GET', 'POST'])
def handle_notes():
    if request.method == 'POST':
        data = request.json
        note = {
            "content": data["content"],
            "timestamp": time.time(),
            "pinned": data.get("pinned", False)
        }
        note_id = notes_ref.push(note).key
        note["id"] = note_id

        # Emit the new note to all connected clients in realtime
        socketio.emit('receive_note', note, broadcast=True)

        return jsonify({"status": "success", "note": note})
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

# REMINDERS ENDPOINTS
@app.route('/api/reminders', methods=['GET', 'POST'])
def handle_reminders():
    if request.method == 'POST':
        data = request.json
        reminder = {
            "content": data["content"],
            "reminder_time": data["reminder_time"],
            "timestamp": time.time()
        }
        reminder_id = reminders_ref.push(reminder).key
        reminder["id"] = reminder_id
        return jsonify({"status": "success", "reminder": reminder})
    else:
        reminders = reminders_ref.get()
        return jsonify(reminders if reminders else {})

@app.route('/api/reminders/<reminder_id>', methods=['PUT', 'DELETE'])
def handle_reminder(reminder_id):
    if request.method == 'PUT':
        data = request.json
        reminders_ref.child(reminder_id).update(data)
        return jsonify({"status": "success"})
    else:
        reminders_ref.child(reminder_id).delete()
        return jsonify({"status": "success"})

# LABELS ENDPOINTS
@app.route('/api/labels', methods=['GET', 'POST'])
def handle_labels():
    if request.method == 'POST':
        data = request.json
        label = {
            "name": data["name"],
            "color": data.get("color", "#ffffff")
        }
        label_id = labels_ref.push(label).key
        label["id"] = label_id
        return jsonify({"status": "success", "label": label})
    else:
        labels = labels_ref.get()
        return jsonify(labels if labels else {})

@app.route('/api/labels/<label_id>', methods=['PUT', 'DELETE'])
def handle_label(label_id):
    if request.method == 'PUT':
        data = request.json
        labels_ref.child(label_id).update(data)
        return jsonify({"status": "success"})
    else:
        labels_ref.child(label_id).delete()
        return jsonify({"status": "success"})

# SOCKET.IO EVENTS (for chat features – unchanged)
@socketio.on('send_message')
def handle_send_message(data):
    message = {
        "content": data["message"],
        "timestamp": time.time(),
        "type": "text"
    }
    if "reply_to" in data and data["reply_to"]:
        message["reply_to"] = data["reply_to"]
        message["reply_text"] = data["reply_text"]
    
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
@socketio.on('delete_message')
def handle_delete_message(data):
    message_id = data.get('id')
    if message_id:
        # Delete the message from Firebase
        messages_ref.child(message_id).delete()
        # Broadcast the deletion to all clients
        emit('message_deleted', message_id, broadcast=True)


@socketio.on('connect')
def handle_connect():
    messages = messages_ref.get()
    if messages:
        for msg_id, msg in messages.items():
            msg["id"] = msg_id
            emit('receive_message', msg)
    
    notes = notes_ref.get()
    if notes:
        for note_id, note in notes.items():
            note["id"] = note_id
            emit('receive_note', note)

@socketio.on('clear_chat')
def handle_clear_chat():
    messages_ref.delete()
    emit('clear_chat', broadcast=True)
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, debug=True, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
