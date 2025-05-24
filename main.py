from moviepy.editor import VideoFileClip, AudioFileClip
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import whisper
import tempfile
import os
from pathlib import Path

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHUNK_DURATION = 300  # seconds (5 minutes)

model = whisper.load_model("base")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    video_path = None
    audio_path = None
    try:
        # Save uploaded video
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            contents = await file.read()
            tmp_video.write(contents)
            video_path = tmp_video.name

        # Extract audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
            audio_path = tmp_audio.name
            video_clip = VideoFileClip(video_path)
            video_clip.audio.write_audiofile(audio_path, codec='pcm_s16le')

        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration

        segments = []
        for start in range(0, int(audio_duration), CHUNK_DURATION):
            end = min(start + CHUNK_DURATION, audio_duration)
            # Create a temporary audio chunk file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as chunk_file:
                chunk_path = chunk_file.name
                # Cut the audio chunk
                chunk_audio = audio_clip.subclip(start, end)
                chunk_audio.write_audiofile(chunk_path, codec='pcm_s16le')
            
            # Transcribe the chunk
            result = model.transcribe(chunk_path)
            segments.append({
                "start": start,
                "end": end,
                "text": result["text"]
            })

            # Clean up chunk file
            if os.path.exists(chunk_path):
                os.remove(chunk_path)

        audio_clip.close()

        return {
            "segments": segments,
            "duration": audio_duration
        }

    except Exception as e:
        print("Transcription error:", e)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        for path in [video_path, audio_path]:
            if path and os.path.exists(path):
                os.remove(path)

@app.get("/")
async def root():
    return {"message": "Video Transcription API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)