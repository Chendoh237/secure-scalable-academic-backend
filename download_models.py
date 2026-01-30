import os
import urllib.request
import bz2
import shutil

# Create ml_models directory if it doesn't exist
os.makedirs("ml_models", exist_ok=True)

# Model URLs and their corresponding filenames
MODELS = {
    "shape_predictor_68_face_landmarks.dat.bz2": "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2",
    "dlib_face_recognition_resnet_model_v1.dat.bz2": "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2"
}

def download_and_extract(url, filename):
    print(f"Downloading {filename}...")
    # Download the file
    urllib.request.urlretrieve(url, filename)
    
    # Extract the .bz2 file
    print(f"Extracting {filename}...")
    with bz2.BZ2File(filename) as fr, open(filename[:-4], "wb") as fw:
        shutil.copyfileobj(fr, fw)
    
    # Remove the .bz2 file
    os.remove(filename)
    print(f"Successfully downloaded and extracted {filename[:-4]}")

def main():
    for filename, url in MODELS.items():
        output_path = os.path.join("ml_models", filename)
        extracted_path = os.path.join("ml_models", filename[:-4])
        
        # Skip if already downloaded and extracted
        if os.path.exists(extracted_path):
            print(f"{extracted_path} already exists, skipping...")
            continue
            
        try:
            download_and_extract(url, output_path)
        except Exception as e:
            print(f"Error downloading {filename}: {e}")

if __name__ == "__main__":
    main()