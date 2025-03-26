from google.cloud import vision
import io

def extract_text(image):
    client = vision.ImageAnnotatorClient()
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    content = img_byte_arr.getvalue()

    image = vision.Image(content=content)
    
    # ✅ 여기 수정됨
    response = client.document_text_detection(image=image)
    
    texts = response.text_annotations
    return texts[0].description if texts else ""
