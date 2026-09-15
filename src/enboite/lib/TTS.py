import json
import os
import secrets
from io import BytesIO
from urllib.parse import quote

import requests

sd = sf = None
try:
    # pyrefly: ignore [missing-import]
    import sounddevice as sd
    
    # pyrefly: ignore [missing-import]
    import soundfile as sf
except ImportError as e:
    print(e)

PT_FILE: str = ""
ENABLE: bool = False

def change() -> None:
    global ENABLE
    
    ENABLE = not ENABLE

def status() -> bool:
    return ENABLE

def ready() -> bool:
    return bool(PT_FILE)

class audio:
    BASE_URL = "http://127.0.0.1:8000"
    SESSION_HTTP = requests.Session()
    
    @staticmethod
    def upload_file(path) -> str:
        with open(path, "rb") as f:
            r = audio.SESSION_HTTP.post(
                f"{audio.BASE_URL}/gradio_api/upload",
                files={"files": f},
            )
        r.raise_for_status()
        return r.json()[0]
    
    @staticmethod
    def wait_for_event(endpoint, event_id):
        with audio.SESSION_HTTP.get(
            f"{audio.BASE_URL}/gradio_api/call/{endpoint}/{event_id}",
            stream=True,
        ) as r:
            r.raise_for_status()
            
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                
                data = line[5:].strip()
                
                if data == "[DONE]":
                    break
                
                result = json.loads(data)
                
                if result is None:
                    continue
                
                return result
                
        raise RuntimeError("Aucun résultat reçu")
    
    @staticmethod
    def download_file(path, output: str = "", memory: bool = False):
        url = f"{audio.BASE_URL}/gradio_api/file={quote(path, safe='/')}"
        
        r = audio.SESSION_HTTP.get(url)
        r.raise_for_status()
        
        if output:
            with open(output, "wb") as f:
                f.write(r.content)
        elif memory:
            return r.content
        else:
            raise RuntimeError("tool:629")

def TTS_make_pt(input: str, ref: str = "", ref_file: str = "", x_vector_only: bool = False) -> str:
    audio_path = audio.upload_file(input)
    r = audio.SESSION_HTTP.post(
        f"{audio.BASE_URL}/gradio_api/call/v2/save_prompt",
        json={
            "ref_aud": {
                "path": audio_path,
                "meta": {
                    "_type": "gradio.FileData"
                },
            },
            "ref_txt": ref or open(ref_file, "r", encoding="utf-8").read(),  # noqa: SIM115
            "use_xvec": x_vector_only,
        },
    )
    
    r.raise_for_status()
    
    pt_path = audio.wait_for_event("save_prompt", r.json()["event_id"])[0]["path"]
    
    out = os.path.join("personal", "TTS", "PT", f"{secrets.token_hex(8)}.pt")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    
    audio.download_file(pt_path, out)
    
    return out

def _TTSspeaker(content: bytes) -> None:
    if sf and sd:
        audio, sample_rate = sf.read(BytesIO(content))
        sd.play(audio, sample_rate)
        sd.wait()

def TTSgen(text: str, pt: str = "") -> bytes:
    """
    permet de générer de l'audio TTS
    text : parole a générer,
    pt : path du fichier pt préalablement générer, ne pas spécifier pour utilise le fichier global définie
    """
    if not pt:
        pt = PT_FILE
    
    r = audio.SESSION_HTTP.post(
        f"{audio.BASE_URL}/gradio_api/call/v2/load_prompt_and_gen",
        json={
            "file_obj": {
                "path": audio.upload_file(pt),
                "meta": {
                    "_type": "gradio.FileData"
                },
            },
            "text": text,
            "lang_disp": "French",
        },
    )
    r.raise_for_status()
    
    result = audio.wait_for_event(
        "load_prompt_and_gen",
        r.json()["event_id"]
    )
    
    output_audio = result[0]
    
    # print("Audio généré :", output_audio["path"])
    # print("Statut :", result[1])
    
    # pyrefly: ignore [bad-return]
    return audio.download_file(
        output_audio["path"], memory=True
    )

def TTS_fix(file: str) -> str:
    global PT_FILE
    PT_FILE = file
    return PT_FILE