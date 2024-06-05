import pytesseract as tess
from PIL import Image

# Set the path to the Tesseract executable
tess.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Open the image
image = Image.open('kerry15.jpg')

# Convert image to string
text = tess.image_to_string(image, lang='tha+eng')

# Print the extracted text
print(text)
