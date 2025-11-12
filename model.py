from flask import Flask, request, jsonify
import json
import datetime
import requests # Added requests for sending violation reports

app = Flask(__name__)

# --- Global State and Configuration ---
# NOTE: In a multi-user system, this state should be managed per car ID (e.g., using a dictionary or database).
# For this example, we use a simple global object to track the last detected sign.
CURRENT_TRAFFIC_SIGN = {"sign": "none", "timestamp": datetime.datetime.now().isoformat()}
SPRINGBOOT_BACKEND_URL = "http://localhost:8081/violations/add" # Placeholder URL, adjust if needed

# Mapping the sign name (from detection model) to the prohibited car action code
# Car Actions: FS=Forward, BS=Backward, RS=Right, LS=Left, Y=Horn
VIOLATION_RULES = {
    # Sign Name: {Prohibited Action: Violation Description}
    "right turn prohibited": {"RS": "right turn prohibited"},
    "left turn prohibited": {"LS": "left turn prohibited"},
    "no entry": {"FS": "no entry"},
    "horn prohibited": {"Y": "horn prohibited"},
}

def send_violation_to_backend(violation_type, detected_sign, action_taken):
    """Sends a structured violation record to the Spring Boot backend."""
    violation_data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "violationType": violation_type,
        "trafficSign": detected_sign,
        "actionTaken": action_taken,
        "carNumber": "Simulator-Car-001" # FIX: Changed 'carId' to 'carNumber' to match Java model
    }
    
    print(f"\n!!! VIOLATION DETECTED: {violation_type} !!!")
    
    try:
        # Use a short timeout to prevent blocking the Flask thread indefinitely
        response = requests.post(
            SPRINGBOOT_BACKEND_URL,
            json=violation_data,
            timeout=5
        )
        if response.status_code == 200 or response.status_code == 201:
            print(f"Successfully reported violation to backend. Response: {response.text}")
        else:
            print(f"Error reporting violation. Backend responded with HTTP {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"CRITICAL ERROR: Could not connect to Spring Boot backend at {SPRINGBOOT_BACKEND_URL}")
    except requests.exceptions.Timeout:
        print("WARNING: Connection timed out while waiting for Spring Boot response.")
    except Exception as e:
        print(f"An unexpected error occurred while reporting violation: {e}")
    print("------------------------------------------\n")

# Route to receive car control actions (from an ESP32 or similar device)
@app.route('/car_action', methods=['POST'])
def car_action():
    """Endpoint for receiving car control commands and checking for violations."""
    global CURRENT_TRAFFIC_SIGN

    try:
        data = request.get_json()
        action_taken = data.get('action')
        current_sign = CURRENT_TRAFFIC_SIGN.get("sign")
        
        log_time = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"[{log_time}] Car Action: {action_taken} | Current Sign: {current_sign}")

        # --- Violation Check Logic ---
        if current_sign in VIOLATION_RULES:
            prohibited_actions = VIOLATION_RULES[current_sign]
            
            # Check if the action taken is one of the prohibited actions for the current sign
            if action_taken in prohibited_actions:
                violation_description = prohibited_actions[action_taken]
                
                # Report the violation to the Spring Boot backend
                send_violation_to_backend(
                    violation_description,
                    current_sign,
                    action_taken
                )
                
                return jsonify({
                    "status": "Violation Detected", 
                    "message": f"Action {action_taken} is prohibited by {current_sign}"
                }), 200

        # If no violation or no relevant sign
        return jsonify({"status": "OK", "message": "Car action received, no violation detected"}), 200
    
    except Exception as e:
        print(f"Error processing car_action: {e}")
        return jsonify({"status": "Error", "message": str(e)}), 400

# NEW ROUTE: Route to accept the detected sign from the video pipeline
@app.route('/detected_sign', methods=['POST'])
def detected_sign():
    """Endpoint for receiving the currently detected sign and updating global state."""
    global CURRENT_TRAFFIC_SIGN
    
    try:
        data = request.get_json()
        sign = data.get('sign')
        confidence = data.get('confidence', 'N/A')

        # Update the global current sign
        CURRENT_TRAFFIC_SIGN["sign"] = sign
        CURRENT_TRAFFIC_SIGN["timestamp"] = datetime.datetime.now().isoformat()
        
        log_time = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"[{log_time}] DETECTED SIGN UPDATED: {sign} (Confidence: {confidence})")

        return jsonify({"status": "OK", "message": f"Sign '{sign}' received and state updated"}), 200
    except Exception as e:
        print(f"Error processing detected_sign: {e}")
        return jsonify({"status": "Error", "message": str(e)}), 400

@app.route('/')
def home():
    return "Violation App is Running"

if __name__ == '__main__':
    # Running on 0.0.0.0 allows access from other devices on the network
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)