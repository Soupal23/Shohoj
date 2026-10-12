
import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(".env", override=True)

api_key = os.getenv("SARVAM_API_KEY")

if not api_key:
    raise ValueError("API key not found in .env")

client = SarvamAI(api_subscription_key=api_key)

with open("question.wav", "rb") as audio:
    response = client.speech_to_text.transcribe(
        file=audio,
        model="saaras:v4",
        language_code="bn-IN",
        mode="transcribe"
    )

print("Transcript:", response.transcript)
print("Language:", response.language_code)
