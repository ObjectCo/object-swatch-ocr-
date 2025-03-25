from google.cloud import vision
import io
import os

def extract_text(image):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/secrets/GOOGLE_APPLICATION_CREDENTIALS"
    client = vision.ImageAnnotatorClient()
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    content = img_byte_arr.getvalue()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts[0].description if texts else ""
