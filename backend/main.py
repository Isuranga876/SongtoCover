import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import List
import replicate

from analyzer import analyze_audio

load_dotenv()

# Initialize Supabase
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("WARNING: Supabase credentials missing in backend/.env")

supabase: Client = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

app = FastAPI(title="Song2Cover API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "song2cover-backend", "supabase_connected": supabase is not None}

@app.post("/api/v1/analyze")
async def analyze_song(
    file: UploadFile = File(...),
    style_preset: str = Form("calm_piano"),
    user_id: str = Form(None)
):
    """
    Phase 2 Endpoint:
    - Saves file locally.
    - Uses librosa to dynamically segment audio structure.
    - Uploads file to Supabase Storage.
    - Creates records in `songs` and `sections`.
    """
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase client not initialized.")

    local_temp_path = None
    try:
        # Create temp dir if not exists
        os.makedirs("temp_uploads", exist_ok=True)
        
        file_ext = file.filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        storage_path = f"uploads/{unique_filename}"
        local_temp_path = os.path.join("temp_uploads", unique_filename)
        
        # 1. Save file locally for analysis
        with open(local_temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Read bytes for Storage upload
        with open(local_temp_path, "rb") as f:
            file_bytes = f.read()

        # 2. Upload to Supabase Storage
        try:
            supabase.storage.from_('songs').upload(
                file=file_bytes,
                path=storage_path,
                file_options={"content-type": file.content_type}
            )
        except Exception as e:
            print(f"Failed to upload to storage bucket 'songs': {e}")
            # Depending on how the user setup supabase, the bucket might not exist yet.
            # We log the error but keep going for the MVP DB insertion.

        # 3. Analyze Audio (Dynamic Segmentation via librosa)
        analysis_data = analyze_audio(local_temp_path, style_preset)

        # 4. Create Song record
        song_data = {
            "original_filename": file.filename,
            "stored_file_path": storage_path,
            "file_type": file.content_type or file_ext,
            "analysis_status": "completed",
            "arrangement_status": "pending",
            "selected_style_preset": style_preset,
            "bpm": analysis_data["bpm"],
            "musical_key": analysis_data["key"]
        }
        
        if user_id:
            song_data["user_id"] = user_id
        
        song_insert = supabase.table("songs").insert(song_data).execute()
        song_id = song_insert.data[0]['id']

        # 5. Create Dynamic Sections DB records
        extracted_sections = analysis_data["sections"]
        
        db_sections = []
        for sec in extracted_sections:
            db_sections.append({
                "song_id": song_id,
                "start_time": sec['start'],
                "end_time": sec['end'],
                "section_label": sec['label'],
                "confidence_score": 0.90, # Heuristic
                "rule_source": "librosa_hpss",
                "vocal_activity_state": sec['label'] == 'vocal'
            })
            
        supabase.table("sections").insert(db_sections).execute()

        return {
            "status": "success",
            "song_id": song_id,
            "filename": file.filename,
            "bpm": analysis_data["bpm"],
            "key": analysis_data["key"],
            "duration": analysis_data.get("duration", 0),
            "sections": extracted_sections,
            "message": "Real audio analysis complete and saved to Supabase."
        }
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 6. Clean up temp file
        # We NO LONGER delete the local temp file so that the generate-track endpoint can use it
        # avoiding Supabase Storage Bucket errors in local setups.
        pass

class GenerateReq(BaseModel):
    song_id: str
    prompt: str = ""

@app.post("/api/v1/generate-track")
async def generate_track(req: GenerateReq):
    song_id = req.song_id
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not connected")
        
    try:
        sections_res = supabase.table("sections").select("*").eq("song_id", song_id).order("start_time").execute()
        if not sections_res.data:
            raise HTTPException(status_code=404, detail="No sections found")
            
        song_res = supabase.table("songs").select("bpm, stored_file_path").eq("id", song_id).execute()
        bpm = song_res.data[0].get("bpm", 120) if song_res.data else 120
        stored_path = song_res.data[0].get("stored_file_path") if song_res.data else None
        
        if not stored_path:
            raise HTTPException(status_code=404, detail="Original song file path missing")
            
        # Instead of downloading from Supabase bucket (which fails if RLS blocks upload initially),
        # we directly read the temp_uploads file that we preserved!
        filename = stored_path.split("/")[-1]
        original_temp_path = os.path.join("temp_uploads", filename)
        
        if not os.path.exists(original_temp_path):
            raise HTTPException(status_code=404, detail="Local audio file missing. Please re-upload and analyze the song again.")
        
        # Replicate Generative AI logic
        if not os.environ.get("REPLICATE_API_TOKEN"):
             raise HTTPException(status_code=500, detail="REPLICATE_API_TOKEN is missing in the .env file. Please add it to generate AI tracks.")
             
        try:
             output = replicate.run(
                 "meta/musicgen-melody:7a76a8258b23fae65c5a22debb8851d2d7e81618ed20b3eb3ee9ef726a7fdd74",
                 input={
                     "melody": open(original_temp_path, "rb"),
                     "prompt": req.prompt if req.prompt else "soft piano and classical guitar instrumental backing track",
                     "duration": 30,
                     "model_version": "stereo"
                 }
             )
             
             if not output:
                 raise Exception("AI model returned empty response.")
                 
             generated_url = output
             
             import requests
             temp_filepath = os.path.join("temp_uploads", f"ai_gen_{song_id}.wav")
             r = requests.get(generated_url)
             with open(temp_filepath, "wb") as f:
                 f.write(r.content)
                 
        except Exception as ai_e:
             print(f"Replicate AI Error: {ai_e}")
             raise HTTPException(status_code=500, detail=f"AI generation failed: {str(ai_e)}")
        
        return FileResponse(
            temp_filepath,
            media_type="audio/wav",
            filename=f"BackingTrack_{song_id}.wav"
        )
    except Exception as e:
        print(f"Error generating track: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
