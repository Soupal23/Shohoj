
import os
import base64
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(".env", override=True)

api_key = os.getenv("SARVAM_API_KEY")

if not api_key:
    raise ValueError("API key not found in .env")

client = SarvamAI(api_subscription_key=api_key)

# Step 1: Speech to Text
with open("question.wav", "rb") as audio:
    stt_response = client.speech_to_text.transcribe(
        file=audio,
        model="saaras:v4",
        language_code="bn-IN",
        mode="transcribe"
    )

question = stt_response.transcript
print("\nYou asked:", question)

# Step 2: Generate AI Answer
chat_response = client.chat.completions(
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant. Answer in natural Bengali. Keep answers concise and conversational."
        },
        {
            "role": "user",
            "content": question
        }
    ],
    model="sarvam-105b-conversations"
)

answer = chat_response.choices[0].message.content
print("\nAI Answer:", answer)

# Step 3: Text to Speech
tts_response = client.text_to_speech.convert(
    text=answer,
    language_code="bn-IN",
    model="bulbul:v3",
    speaker="roopa"
)

audio_data = base64.b64decode(tts_response.audios[0])

with open("answer.wav", "wb") as audio_file:
    audio_file.write(audio_data)

print("\nBot's spoken answer saved to answer.wav")
