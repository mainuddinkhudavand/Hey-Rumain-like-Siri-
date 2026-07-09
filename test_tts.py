# ============================================================
#  test_tts.py — Text-To-Speech Playback Diagnostic
# ============================================================
import asyncio
import os
import tempfile

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

async def test_speech():
    print("=" * 60)
    print("  RUMAIN Diagnostic — TTS Voice Playback Test")
    print("=" * 60)
    
    text = "Hello! My name is Rumain. Your new desktop voice assistant is ready to help you."
    voice = "en-US-EmmaMultilingualNeural" # Soft female voice
    
    print(f"Streaming speech from Edge-TTS using voice: {voice}...")
    
    try:
        import edge_tts
        pygame.mixer.init()
        
        fd, temp_file = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_file)
        
        print("Playing audio via Pygame mixer...")
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
        pygame.mixer.music.unload()
        os.remove(temp_file)
        print("Voice playback diagnostic complete!")
        
    except ImportError:
        print("edge-tts or pygame is not installed. Please check requirements.")
    except Exception as e:
        print(f"Speech diagnostic failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_speech())
