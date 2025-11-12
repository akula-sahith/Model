from inference import InferencePipeline
import cv2
import requests
import time

# --- Configuration ---
# Set the URL for the new Flask endpoint
FLASK_SERVER_URL = "http://127.0.0.1:5000/detected_sign"
# Throttle setting: only send a POST request every X seconds to prevent spamming the server
POST_DELAY_SECONDS = 2.0 

# Global state variables
last_post_time = 0 
last_sent_sign = None # NEW: Tracks the name of the last sign successfully sent to the server

def my_sink(result, video_frame):
    global last_post_time
    global last_sent_sign # Access the new global variable
    
    # --- Display Image ---
    if result.get("output_image"):
        cv2.imshow("Workflow Image", result["output_image"].numpy_image)
        cv2.waitKey(1)

    # --- Sign Detection and Flask Communication Logic ---
    predictions = result.get("predictions")
    
    if predictions and predictions.data.get('class_name') is not None:
        class_names = predictions.data['class_name']
        confidences = predictions.confidence
        
        # Check if detections are present
        if len(class_names) > 0:
            current_time = time.time()
            
            # 1. Identify the highest confidence detection
            highest_confidence_index = confidences.argmax()
            detected_sign = class_names[highest_confidence_index]
            confidence = float(confidences[highest_confidence_index])
            
            # 2. Check if the sign is DIFFERENT from the last one sent
            is_new_sign = detected_sign != last_sent_sign
            
            # 3. Check if enough time has passed since the last post (throttling)
            is_post_due = current_time - last_post_time >= POST_DELAY_SECONDS
            
            # Send condition: New sign detected AND throttling delay has passed
            if is_new_sign and is_post_due:
                
                print(f"NEW SIGN DETECTED: {detected_sign} | Confidence: {confidence:.2f}")
                
                try:
                    # POST the detected sign to the Flask endpoint
                    response = requests.post(
                        FLASK_SERVER_URL, 
                        json={'sign': detected_sign, 'confidence': confidence}
                    )
                    
                    if response.status_code == 200:
                        print(f"Successfully sent new sign '{detected_sign}' to Flask server.")
                        # Update state variables upon successful send
                        last_post_time = current_time
                        last_sent_sign = detected_sign
                    else:
                        print(f"Error sending sign: HTTP {response.status_code}")
                        
                except requests.exceptions.ConnectionError:
                    print(f"Could not connect to Flask server at {FLASK_SERVER_URL}. Is it running?")
                except Exception as e:
                    print(f"An unexpected error occurred during POST: {e}")
            else:
                # Sign detected, but either it's the same sign, or throttling is active
                reason = "Same sign" if not is_new_sign else f"Throttling (wait {POST_DELAY_SECONDS - (current_time - last_post_time):.2f}s)"
                print(f"Sign detected ({detected_sign}), skipping post. Reason: {reason}")
        
        elif len(class_names) == 0 and last_sent_sign is not None:
            # If nothing is detected, but we last sent a sign, we can send a "clear" signal 
            # (optional, but good for car control)
            if current_time - last_post_time >= POST_DELAY_SECONDS:
                detected_sign = "NONE"
                print("No signs detected. Sending 'NONE' signal to server.")
                try:
                    response = requests.post(
                        FLASK_SERVER_URL, 
                        json={'sign': detected_sign, 'confidence': 1.0}
                    )
                    if response.status_code == 200:
                        print("Successfully sent 'NONE' signal.")
                        last_post_time = current_time
                        last_sent_sign = detected_sign # Update last sent sign to NONE
                except requests.exceptions.ConnectionError:
                    pass # Ignore connection errors here to avoid spamming console
                except Exception as e:
                    print(f"Error sending 'NONE' signal: {e}")
            # else: 
                # Throttling prevents sending 'NONE' yet.
    # else:
        # print("No detections or prediction data.")

# 2. Initialize a pipeline object
# NOTE: Ensure your webcam (device 0) is accessible and Flask is running
pipeline = InferencePipeline.init_with_workflow(
    api_key="VpNikn8iPG24trcSdIrm",
    workspace_name="epics-hzvjt",
    workflow_id="detect-count-and-visualize-4",
    video_reference=0, # Path to video, device id (int, usually 0 for built in webcams), or RTSP stream url
    max_fps=30,
    on_prediction=my_sink
)

# 3. Start the pipeline and wait for it to finish
print("Starting video pipeline. Ensure Flask server is running at http://127.0.0.1:5000")
pipeline.start()
pipeline.join()