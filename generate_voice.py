
import os
import base64
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(".env", override=True)

api_key = os.getenv("SARVAM_API_KEY")

if not api_key:
    raise ValueError("SARVAM_API_KEY not found in .env file")

client = SarvamAI(api_subscription_key=api_key)


text = """নমস্কার। আমি লক্ষ্মীর ভাণ্ডার প্রকল্পে আবেদন করতে চাই।
আমার কাছে আধার কার্ড আর ভোটার কার্ড আছে।
কিন্তু ফর্মটা কীভাবে পূরণ করব, আর কী কী কাগজ লাগবে,
তা আমি জানি না। ফর্মটা কোথায় জমা দিতে হবে,
সেটাও একটু সহজ করে বুঝিয়ে বলবেন?
"""


response = client.text_to_speech.convert(
    text=text,
    model="bulbul:v3",
    language_code="bn-IN",
    speaker="roopa"
)

audio_bytes = base64.b64decode(response.audios[0])

output_file = "user_question.wav"

with open(output_file, "wb") as f:
    f.write(audio_bytes)

print(f"Voice generated successfully: {output_file}")
