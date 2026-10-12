# Shohoj (সহজ)

### Making the Complicated Simple.

Shohoj is a Bengali-first, voice-enabled AI assistant designed to make government forms and application processes easier to understand for rural communities and people who face language or literacy barriers.

Government forms can be difficult to navigate. People may struggle to understand form fields, identify the required documents, or figure out where to submit an application. Shohoj aims to bridge this gap by allowing users to upload a government form, explain their situation in their own language, and receive simple, step-by-step guidance.

## The Problem

Many people find government application processes confusing because of:

- Complex instructions and unfamiliar administrative terminology.
- Uncertainty about the documents required for an application.
- Difficulty understanding how to fill out forms correctly.
- Lack of clarity about where and how to submit completed forms.
- Language and literacy barriers that make written instructions inaccessible.

## Key Features

- **Government Form Understanding:** Upload a government form or document so the application can extract its text and use it as context for assistance.
- **Voice-Based Interaction:** Process spoken questions using Bengali speech recognition, making the experience more accessible to users who find typing difficult.
- **Simple, Step-by-Step Guidance:** Use an AI language model to turn complex instructions into explanations that are easier to follow.
- **Bengali Text-to-Speech:** Convert generated answers into spoken Bengali so users can listen instead of relying entirely on written instructions.
- **Multilingual Interface:** Provide bilingual Bengali and English labels to make the interface easier to navigate.
- **Audio-Based Accessibility:** Support a voice-first workflow that reduces dependence on traditional text-based interaction.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic and API integration |
| Gradio | Interactive web interface |
| Sarvam AI Speech-to-Text | Transcribes spoken Bengali questions |
| Sarvam AI Language Model | Generates contextual explanations and action plans |
| Sarvam AI Text-to-Speech | Converts responses into spoken Bengali |
| Sarvam AI Document Processing / OCR | Extracts text from uploaded government forms |
| python-dotenv | Loads API credentials securely from environment variables |

## API Overview

Shohoj uses Sarvam AI APIs to connect document understanding, speech recognition, language generation, and speech synthesis into one workflow.

### 1. Document Processing

**Purpose:** Extract text from uploaded government forms and documents.

The extracted content provides context for the language model, helping it explain form fields and application instructions.

- **Input:** Uploaded government document, such as a supported PDF or image.
- **Processing:** Document text extraction / OCR.
- **Output:** Extracted text used as context for the response.

### 2. Speech-to-Text (STT)

**Purpose:** Convert the user's spoken question into text.

- **Model:** `saaras:v4`
- **Language:** `bn-IN` (Bengali)
- **Input:** Audio recording.
- **Output:** Transcribed Bengali text.

Example:

```python
response = client.speech_to_text.transcribe(
    file=audio,
    model="saaras:v4",
    language_code="bn-IN",
    mode="transcribe"
)
```

The current transcription workflow has a 30-second audio limit; longer recordings may require Sarvam's batch transcription API.

### 3. Language Model

**Purpose:** Understand the user's question alongside the extracted document text and generate a helpful response.

- **Model:** `sarvam-105b-conversations`
- **Input:** User's transcribed question and relevant document text.
- **Output:** A simple explanation and suggested next steps in the selected response language.

The document text should be supplied as context so the response can be grounded in the uploaded form rather than relying only on general knowledge.

### 4. Text-to-Speech (TTS)

**Purpose:** Read the generated response aloud in Bengali.

- **Model:** `bulbul:v3`
- **Language:** `bn-IN`
- **Speaker:** `roopa`
- **Input:** Generated Bengali response.
- **Output:** Audio that can be played by the user.

Example:

```python
response = client.text_to_speech.convert(
    text=answer,
    model="bulbul:v3",
    language_code="bn-IN",
    speaker="roopa"
)
```

### End-to-End Workflow

```text
Upload Government Form
          |
          v
Extract Document Text
          |
          v
User Speaks a Question
          |
          v
Speech-to-Text (STT)
          |
          v
Combine Question + Document Context
          |
          v
Sarvam AI Language Model
          |
          v
Simple, Step-by-Step Answer
          |
          v
Text-to-Speech (TTS)
          |
          v
User Listens to the Answer
```

## Setup and Installation

### Prerequisites

- Python 3.10 or a compatible version supported by the installed dependencies.
- A Sarvam AI API key.
- Git.

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/shohoj.git
cd shohoj
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
SARVAM_API_KEY=your_sarvam_api_key
```

Never commit your `.env` file or expose your API key publicly.

### 4. Run the Application

```bash
python app.py
```

Open the local Gradio URL displayed in the terminal.

## Responsible Use

Shohoj is intended to improve access to information, not replace official government authorities. Scheme eligibility, required documents, deadlines, and submission procedures can change. Users should verify important details with the relevant government department or authorized service centre before submitting an application.

## Vision

Shohoj aims to make essential public information more accessible by allowing people to ask questions naturally and understand complicated procedures in a language they are comfortable with.

**Making the complicated simple, one conversation at a time.**
