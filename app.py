
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


# --- Modern Theme & Visual System ---
custom_theme = gr.themes.Soft(
    primary_hue=gr.themes.colors.emerald,
    secondary_hue=gr.themes.colors.teal,
    neutral_hue=gr.themes.colors.slate,
)

custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

* {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

.gradio-container {
    max-width: 1280px !important;
    margin: 0 auto !important;
    padding: 1.5rem 1rem !important;
    font-family: 'Plus Jakarta Sans', 'Hind Siliguri', system-ui, sans-serif !important;
}

/* Hero Header */
.hero-box {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(240, 253, 244, 0.92) 50%, rgba(240, 249, 255, 0.98) 100%);
    border: 1px solid rgba(16, 185, 129, 0.22);
    border-radius: 24px;
    padding: 2.25rem 2rem 2rem;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px -10px rgba(5, 150, 105, 0.09), 0 4px 6px -2px rgba(0, 0, 0, 0.02);
    position: relative;
    overflow: hidden;
}

.hero-box::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, #059669, #0d9488, #0284c7, #6366f1);
}

.hero-badge-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(5, 150, 105, 0.08);
    border: 1px solid rgba(5, 150, 105, 0.25);
    color: #047857;
    padding: 6px 14px;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.85rem;
}

.pulse-dot {
    width: 8px;
    height: 8px;
    background-color: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% {
        transform: scale(0.95);
        box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
    }
    70% {
        transform: scale(1);
        box-shadow: 0 0 0 7px rgba(16, 185, 129, 0);
    }
    100% {
        transform: scale(0.95);
        box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
    }
}

.hero-title {
    font-size: 2.75rem;
    font-weight: 800;
    line-height: 1.15;
    margin: 0 0 0.5rem;
    color: #0f172a;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.hero-title-bn {
    background: linear-gradient(135deg, #047857 0%, #0d9488 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-family: 'Hind Siliguri', 'Plus Jakarta Sans', sans-serif;
}

.hero-title-sep {
    color: #cbd5e1;
    font-weight: 300;
}

.hero-title-en {
    color: #1e293b;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.hero-tagline {
    font-size: 1.08rem;
    color: #475569;
    margin: 0 0 1.15rem;
    font-weight: 500;
    line-height: 1.5;
}

.hero-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 0.75rem;
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    color: #334155;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

/* Card Sections */
.glass-card {
    background: #ffffff !important;
    border: 1px solid rgba(226, 232, 240, 0.9) !important;
    border-radius: 18px !important;
    padding: 18px !important;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04) !important;
    margin-bottom: 1rem !important;
    transition: all 0.2s ease-in-out !important;
}

.glass-card:hover {
    border-color: rgba(16, 185, 129, 0.35) !important;
    box-shadow: 0 8px 24px -4px rgba(15, 23, 42, 0.07) !important;
}

/* Step Header */
.step-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #f1f5f9;
}

.step-num-pill {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #059669 0%, #0d9488 100%);
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(5, 150, 105, 0.25);
    flex-shrink: 0;
}

.step-info h3 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: #0f172a;
}

.step-info p {
    margin: 2px 0 0;
    font-size: 0.82rem;
    color: #64748b;
}

/* Submit Button */
.cta-submit-btn {
    margin-top: 0.75rem !important;
    margin-bottom: 0.5rem !important;
}

.cta-submit-btn button {
    background: linear-gradient(135deg, #059669 0%, #0d9488 50%, #0284c7 100%) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 1.08rem !important;
    padding: 16px 28px !important;
    border-radius: 14px !important;
    border: none !important;
    box-shadow: 0 8px 24px -4px rgba(5, 150, 105, 0.4) !important;
    cursor: pointer !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    width: 100% !important;
}

.cta-submit-btn button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 28px -4px rgba(5, 150, 105, 0.55) !important;
    filter: brightness(1.05) !important;
}

.cta-submit-btn button:active {
    transform: translateY(0px) !important;
}

/* Right Output Column */
.output-card {
    background: #ffffff !important;
    border: 1px solid rgba(226, 232, 240, 0.9) !important;
    border-radius: 18px !important;
    padding: 20px !important;
    box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05) !important;
}

.output-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
}

.output-title-wrap h3 {
    margin: 0;
    font-size: 1.18rem;
    font-weight: 800;
    color: #0f172a;
}

.output-title-wrap p {
    margin: 3px 0 0;
    font-size: 0.83rem;
    color: #64748b;
}

.status-badge {
    background: #ecfdf5;
    color: #047857;
    border: 1px solid #a7f3d0;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 9999px;
    letter-spacing: 0.03em;
}

/* Audio Player */
.audio-card {
    background: linear-gradient(135deg, #f0fdf4 0%, #f0f9ff 100%) !important;
    border: 1px solid rgba(16, 185, 129, 0.2) !important;
    border-radius: 14px !important;
    padding: 10px !important;
    margin-bottom: 14px !important;
}

/* Textboxes */
.guidance-textbox textarea {
    font-size: 0.98rem !important;
    line-height: 1.65 !important;
    color: #1e293b !important;
    background: #fbfcfe !important;
    border-radius: 12px !important;
    font-family: 'Plus Jakarta Sans', 'Hind Siliguri', system-ui, sans-serif !important;
}

/* Disclaimer Footer */
.disclaimer-banner {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 18px 22px;
    margin-top: 1.75rem;
}

.disclaimer-icon {
    font-size: 1.4rem;
    line-height: 1;
    flex-shrink: 0;
    margin-top: 2px;
}

.disclaimer-text h4 {
    margin: 0 0 4px;
    font-size: 0.88rem;
    font-weight: 700;
    color: #334155;
}

.disclaimer-text p {
    margin: 0;
    font-size: 0.82rem;
    color: #64748b;
    line-height: 1.55;
}

/* Dark mode compatibility */
@media (prefers-color-scheme: dark) {
    .hero-box {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%) !important;
        border-color: rgba(51, 65, 85, 0.8) !important;
    }
    .hero-title-en {
        color: #f8fafc !important;
    }
    .hero-tagline {
        color: #94a3b8 !important;
    }
    .chip {
        background: #1e293b !important;
        border-color: #334155 !important;
        color: #cbd5e1 !important;
    }
    .glass-card, .output-card {
        background: #1e293b !important;
        border-color: #334155 !important;
    }
    .step-info h3, .output-title-wrap h3 {
        color: #f8fafc !important;
    }
    .disclaimer-banner {
        background: #0f172a !important;
        border-color: #1e293b !important;
    }
    .disclaimer-text h4 {
        color: #cbd5e1 !important;
    }
    .disclaimer-text p {
        color: #94a3b8 !important;
    }
}
"""

with gr.Blocks(title="Shohoj | সহজ") as demo:
    # Inject Custom CSS Stylesheet
    gr.HTML(f"<style>{custom_css}</style>")

    # Top Hero Banner
    gr.HTML(
        """
        <div class="hero-box">
            <div class="hero-badge-pill">
                <span class="pulse-dot"></span>
                SARVAM AI CIVIC ASSISTANT • সরকারি ফর্ম সহায়ক
            </div>
            <h1 class="hero-title">
                <span class="hero-title-bn">সহজ</span>
                <span class="hero-title-sep">/</span>
                <span class="hero-title-en">Shohoj</span>
            </h1>
            <p class="hero-tagline">
                জটিল বিষয় সহজ করে বুঝুন • Making Complex Government Documents Simple & Actionable
            </p>
            <div class="hero-chips">
                <span class="chip">📄 Sarvam Doc AI</span>
                <span class="chip">🎙️ Saaras STT</span>
                <span class="chip">🧠 Sarvam-105B Reasoning</span>
                <span class="chip">🔊 Bulbul Voice TTS</span>
                <span class="chip">🌐 বাংলা • हिन्दी • English</span>
            </div>
        </div>
        """
    )

    with gr.Row(equal_height=False):
        # LEFT COLUMN: Inputs & Controls
        with gr.Column(scale=5):
            # Step 1: Upload Form
            with gr.Group(elem_classes=["glass-card"]):
                gr.HTML(
                    """
                    <div class="step-banner">
                        <div class="step-num-pill">১</div>
                        <div class="step-info">
                            <h3>১. সরকারি ফর্ম আপলোড করুন</h3>
                            <p>Upload your government form (PDF max 10 pages, PNG, or JPG)</p>
                        </div>
                    </div>
                    """
                )
                document_input = gr.File(
                    label="ফর্ম আপলোড করুন / Upload form",
                    file_types=[".pdf", ".png", ".jpg", ".jpeg"],
                    type="filepath",
                )
                document_language = gr.Dropdown(
                    choices=[
                        ("বাংলা / Bengali", "bn-IN"),
                        ("হিন্দি / Hindi", "hi-IN"),
                        ("ইংরেজি / English", "en-IN")
                    ],
                    value="bn-IN",
                    label="ফর্মের ভাষা / Document language",
                )

            # Step 2: Voice & Situation
            with gr.Group(elem_classes=["glass-card"]):
                gr.HTML(
                    """
                    <div class="step-banner">
                        <div class="step-num-pill">২</div>
                        <div class="step-info">
                            <h3>২. আপনার পরিস্থিতি বলুন</h3>
                            <p>Record your voice explaining your situation (Keep under 30 seconds)</p>
                        </div>
                    </div>
                    """
                )
                audio_input = gr.Audio(
                    sources=["microphone", "upload"],
                    type="filepath",
                    label="আপনার কথা রেকর্ড করুন / Record your voice",
                )
                with gr.Row():
                    input_language = gr.Dropdown(
                        choices=[
                            ("বাংলা / Bengali", "bn-IN"),
                            ("হিন্দি / Hindi", "hi-IN")
                        ],
                        value="bn-IN",
                        label="আপনি কোন ভাষায় বলবেন? / Spoken language",
                    )
                    response_language = gr.Dropdown(
                        choices=[
                            ("বাংলা / Bengali", "bn-IN"),
                            ("হিন্দি / Hindi", "hi-IN")
                        ],
                        value="bn-IN",
                        label="উত্তরের ভাষা / Response language",
                    )

            # Action Button
            submit = gr.Button(
                "✨ সহজ করে বুঝিয়ে বলুন / Explain it simply",
                variant="primary",
                size="lg",
                elem_classes=["cta-submit-btn"],
            )

        # RIGHT COLUMN: Results & Audio Guidance
        with gr.Column(scale=6):
            with gr.Group(elem_classes=["output-card"]):
                gr.HTML(
                    """
                    <div class="output-header">
                        <div class="output-title-wrap">
                            <h3>সহজের পরামর্শ ও সমাধান</h3>
                            <p>Shohoj's Guidance & Action Plan</p>
                        </div>
                        <span class="status-badge">AI Verified Guidance</span>
                    </div>
                    """
                )

                # Audio Guidance Output
                audio_output = gr.Audio(
                    label="উত্তর শুনুন / Listen to the answer",
                    autoplay=False,
                    elem_classes=["audio-card"],
                )

                # Action Plan Text
                answer_output = gr.Textbox(
                    label="আপনার করণীয় / Your action plan",
                    lines=12,
                    elem_classes=["guidance-textbox"],
                )

                # Extracted OCR text in an accordion for clean aesthetics
                with gr.Accordion(
                    "📄 ফর্ম থেকে পড়া মূল লেখা দেখুন / Text extracted from the form",
                    open=False,
                ):
                    extracted_output = gr.Textbox(
                        label="ফর্ম থেকে পড়া লেখা / Text extracted from the form",
                        lines=8,
                    )

    # Event binding (exact same functionality and signatures)
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

    # Bottom Disclaimer Banner
    gr.HTML(
        """
        <div class="disclaimer-banner">
            <div class="disclaimer-icon">🛡️</div>
            <div class="disclaimer-text">
                <h4>সতর্কতা / Disclaimer</h4>
                <p>
                    এটি সরকারি তথ্য বুঝতে সাহায্য করার একটি সহায়ক ব্যবস্থা।
                    অনিশ্চিত তথ্য সংশ্লিষ্ট সরকারি দপ্তরে যাচাই করুন।
                    <br>
                    This tool helps you understand government information. Verify uncertain information with the relevant government office.
                </p>
            </div>
        </div>
        """
    )


demo.launch(theme=custom_theme, css=custom_css)

