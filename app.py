
import os
import time
import base64
import tempfile
import mimetypes
import zipfile
import io
import requests
import gradio as gr
from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv(".env", override=True)

api_key = os.getenv("SARVAM_API_KEY")
if not api_key:
    raise ValueError("API key not found in .env")

client = SarvamAI(api_subscription_key=api_key)


def extract_document_text(file_path, document_language):
    """Extract text from an uploaded PDF or image using Sarvam Document AI."""

    if not file_path:
        raise ValueError(
            "Please upload a government form. / "
            "দয়া করে একটি সরকারি ফর্ম আপলোড করুন।"
        )

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0]

    if content_type not in ("application/pdf", "image/png", "image/jpeg"):
        raise ValueError(
            "Unsupported file type. Upload a PDF, PNG or JPG. / "
            "এই ফাইলটি সমর্থিত নয়। PDF, PNG অথবা JPG আপলোড করুন।"
        )

    with open(file_path, "rb") as document:
        job = client.doc_ai.digitise(
            file=[(filename, document, content_type)],
            language=document_language,
            output_format="md"
        )

    # Document processing happens asynchronously.
    terminal_states = {
        "completed", "partially_completed", "failed", "rejected"
    }

    status = None

    for _ in range(36):  # Wait up to approximately 3 minutes.
        status = client.doc_ai.get_status(job_id=job.job_id)

        if status.status.lower() in terminal_states:
            break

        time.sleep(5)

    if status is None or status.status.lower() not in (
        "completed", "partially_completed"
    ):
        raise RuntimeError(
            "Document processing did not finish successfully. "
            "Please try again with a smaller or clearer document. / "
            "ফর্মটি পড়া যায়নি। ছোট বা পরিষ্কার ফাইল দিয়ে আবার চেষ্টা করুন।"
        )

    download = client.doc_ai.get_download_url(job_id=job.job_id)

    response = requests.get(download.url, timeout=60)
    response.raise_for_status()

    # Sarvam returns a ZIP containing the extracted document text.
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()

        text_files = [
            name for name in names
            if name.lower().endswith((".md", ".txt"))
            and not name.startswith("__MACOSX/")
        ]

        if not text_files:
            raise RuntimeError(
                "OCR completed, but no text file was found in the result."
            )

        # Prefer Markdown, which preserves document structure.
        text_files.sort(
            key=lambda name: (
                not name.lower().endswith(".md"),
                name.count("/")
            )
        )

        extracted_text = archive.read(text_files[0]).decode(
            "utf-8", errors="replace"
        ).strip()

    if not extracted_text:
        raise RuntimeError(
            "No readable text was found. Please upload a clearer document."
        )

    return extracted_text


def voice_bot(
    audio_path,
    document_path,
    document_language,
    input_language,
    response_language
):
    if document_path is None:
        return (
            "Please upload a government form first. / "
            "প্রথমে একটি সরকারি ফর্ম আপলোড করুন।",
            "",
            None
        )

    if audio_path is None:
        return (
            "Please record your situation. / "
            "দয়া করে আপনার পরিস্থিতি রেকর্ড করুন।",
            "",
            None
        )

    try:
        # Step 1: Extract text from the uploaded government document.
        form_text = extract_document_text(
            document_path, document_language
        )

        # Step 2: Transcribe the user's voice in the selected language.
        with open(audio_path, "rb") as audio:
            stt_response = client.speech_to_text.transcribe(
                file=audio,
                model="saaras:v4",
                language_code=input_language,
                mode="transcribe"
            )

        question = stt_response.transcript

        language_name = {
            "bn-IN": "simple, everyday Bengali",
            "hi-IN": "simple, everyday Hindi"
        }[response_language]

        # Step 3: Generate practical guidance using the document text.
        chat_response = client.chat.completions(
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are Shohoj (সহজ), a voice assistant helping people
understand government forms and public services.

Reply in {language_name}.

Use short, clear sentences and numbered action steps.
Keep the response concise and easy to understand.

IMPORTANT RULES:
- Treat the extracted document as the source of information
  about what the document says.
- The user's spoken statement explains their situation.
- Do not assume that the document contains every government
  procedure or eligibility requirement.
- Never invent documents, fees, deadlines, addresses,
  eligibility rules, or application procedures.
- Explain where to obtain a document only if reliable
  supporting information is available in the supplied text.
- If information is missing, say what must be confirmed
  and with which relevant government office or authority.
- Do not claim that the user qualifies for a scheme unless
  the available evidence supports that conclusion.
- If OCR text is unclear or incomplete, mention that.
- Give a concise, practical action plan.
- End with a reminder to verify uncertain details officially.

Use this structure in the selected language:
1. What the document is about.
2. What the user should do next.
3. Which documents may be needed, if confirmed.
4. What needs to be verified.
"""
                },
                {
                    "role": "user",
                    "content": f"""
EXTRACTED GOVERNMENT DOCUMENT TEXT:
{form_text[:18000]}

USER'S SPOKEN SITUATION:
{question}

Explain the document in the context of the user's situation.
Give practical next steps without inventing missing information.
"""
                }
            ],
            model="sarvam-105b-conversations"
        )

        answer = chat_response.choices[0].message.content

        if not answer:
            raise RuntimeError("The assistant returned an empty answer.")

        transcript_label = (
            "আপনার বলা কথা / Your spoken situation"
        )
        answer_label = (
            "সহজের পরামর্শ / Shohoj's guidance"
        )

        result = (
            f"{transcript_label}\n{question}\n\n"
            f"{answer_label}\n{answer}"
        )

        # Step 4: Generate speech separately.
        # If TTS fails, preserve the written guidance.
        output_path = None

        try:
            tts_response = client.text_to_speech.convert(
                text=answer,
                language_code=response_language,
                model="bulbul:v3",
                speaker="roopa"
            )

            audio_data = base64.b64decode(tts_response.audios[0])

            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as output_file:
                output_file.write(audio_data)
                output_path = output_file.name

        except Exception as tts_error:
            result += (
                "\n\nVoice generation failed. "
                "The written guidance is still available.\n"
                f"Details: {tts_error}"
            )

        return result, form_text[:12000], output_path

    except Exception as e:
        return (
            f"An error occurred / সমস্যা হয়েছে:\n{str(e)}",
            "",
            None
        )


with gr.Blocks(title="Shohoj | সহজ") as demo:
    gr.Markdown(
        """
        # সহজ | Shohoj
        ### জটিল বিষয় সহজ করে বুঝুন
        ### Making the complicated simple.

        সরকারি ফর্ম বুঝতে অসুবিধা হচ্ছে?
        / Having trouble understanding a government form?

        ফর্ম আপলোড করুন, নিজের পরিস্থিতি বলুন।
        / Upload the form and describe your situation.
        """
    )

    gr.Markdown(
        """
        ## ১. সরকারি ফর্ম আপলোড করুন
        ## 1. Upload your government form

        PDF, PNG বা JPG ফাইল দিন (PDF সর্বোচ্চ ১০ পৃষ্ঠা)।
        / Upload a PDF, PNG or JPG file (PDFs: maximum 10 pages).
        """
    )

    document_input = gr.File(
        label="ফর্ম আপলোড করুন / Upload form",
        file_types=[".pdf", ".png", ".jpg", ".jpeg"],
        type="filepath"
    )

    document_language = gr.Dropdown(
        choices=[
            ("বাংলা / Bengali", "bn-IN"),
            ("হিন্দি / Hindi", "hi-IN"),
            ("ইংরেজি / English", "en-IN")
        ],
        value="bn-IN",
        label="ফর্মের ভাষা / Document language"
    )

    gr.Markdown(
        """
        ## ২. আপনার পরিস্থিতি বলুন
        ## 2. Describe your situation

        মাইক্রোফোনে আপনার কী সাহায্য প্রয়োজন তা বলুন।
        / Record your voice and explain what help you need.

        Keep your recording under 30 seconds.
        / আপনার রেকর্ডিং ৩০ সেকেন্ডের কম রাখুন।
        """
    )

    audio_input = gr.Audio(
        sources=["microphone", "upload"],
        type="filepath",
        label="আপনার কথা রেকর্ড করুন / Record your voice"
    )

    input_language = gr.Dropdown(
        choices=[
            ("বাংলা / Bengali", "bn-IN"),
            ("হিন্দি / Hindi", "hi-IN")
        ],
        value="bn-IN",
        label="আপনি কোন ভাষায় বলবেন? / Spoken language"
    )

    response_language = gr.Dropdown(
        choices=[
            ("বাংলা / Bengali", "bn-IN"),
            ("হিন্দি / Hindi", "hi-IN")
        ],
        value="bn-IN",
        label="উত্তরের ভাষা / Response language"
    )

    submit = gr.Button(
        "সহজ করে বুঝিয়ে বলুন / Explain it simply",
        variant="primary"
    )

    answer_output = gr.Textbox(
        label="আপনার করণীয় / Your action plan",
        lines=12
    )

    extracted_output = gr.Textbox(
        label="ফর্ম থেকে পড়া লেখা / Text extracted from the form",
        lines=8
    )

    audio_output = gr.Audio(
        label="উত্তর শুনুন / Listen to the answer",
        autoplay=False
    )

    submit.click(
        fn=voice_bot,
        inputs=[
            audio_input,
            document_input,
            document_language,
            input_language,
            response_language
        ],
        outputs=[
            answer_output,
            extracted_output,
            audio_output
        ]
    )

    gr.Markdown(
        """
        ---
        **সতর্কতা / Disclaimer**

        এটি সরকারি তথ্য বুঝতে সাহায্য করার একটি সহায়ক ব্যবস্থা।
        / This tool helps you understand government information.

        অনিশ্চিত তথ্য সংশ্লিষ্ট সরকারি দপ্তরে যাচাই করুন।
        / Verify uncertain information with the relevant government office.
        """
    )


demo.launch()
