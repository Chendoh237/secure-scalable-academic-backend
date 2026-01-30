# test_face_recognition.py
import cv2
import os
from recognition.face_utils import FaceProcessor

def main():
    # Initialize the face processor
    print("Initializing FaceProcessor...")
    processor = FaceProcessor()
    print("FaceProcessor initialized successfully!")

    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to your test image (place it in the same directory as this script)
    image_path = os.path.join(script_dir, "test_image.jpg")
    
    # Load the image
    print(f"Loading image from {image_path}...")
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"Error: Could not load image at {image_path}")
        print("Please make sure the image exists and the path is correct.")
        return
    
    print("Detecting faces...")
    # Detect faces
    faces = processor.detect_faces(image)
    print(f"Found {len(faces)} face(s) in the image")
    
    if not faces:
        print("No faces detected. Try another image or check the image quality.")
        return
    
    # Get face encodings
    print("Extracting face encodings...")
    encodings = processor.get_face_encodings(image, faces)
    print(f"Extracted {len(encodings)} face encoding(s)")
    
    # Draw rectangles around the faces
    for face in faces:
        (x, y, w, h) = face['box']
        cv2.rectangle(image, (x, y), (x+w, y+h), (0, 255, 0), 2)
    
    # Save the result
    output_path = os.path.join(script_dir, "detected_faces.jpg")
    cv2.imwrite(output_path, image)
    print(f"Result saved to {output_path}")

if __name__ == "__main__":
    main()