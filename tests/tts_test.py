
import os
import base64
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(".env", override=True)

api_key = os.getenv("SARVAM_API_KEY")

if not api_key:
    raise ValueError("API key not found in .env")

client = SarvamAI(api_subscription_key=api_key)

text = "নমস্কার! আমি আপনার বাংলা ভয়েস বট। কলকাতা একটি সুন্দর শহর।"

response = client.text_to_speech.convert(
    text=text,
    language_code="bn-IN",
    model="bulbul:v3",
    speaker="roopa"
)

audio_data = base64.b64decode(response.audios[0])

with open("answer.wav", "wb") as audio_file:
    audio_file.write(audio_data)

print("Speech generated successfully! Saved as answer.wav")
