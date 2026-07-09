# ============================================================
#  test_microphone.py — PyAudio Microphone Diagnostic
# ============================================================
import pyaudio

def test_mic():
    print("=" * 60)
    print("  RUMAIN Diagnostic — Microphone Input Verification")
    print("=" * 60)
    
    p = pyaudio.PyAudio()
    device_count = p.get_device_count()
    print(f"\nFound {device_count} audio devices:")
    
    default_input_idx = None
    try:
        default_info = p.get_default_input_device_info()
        default_input_idx = default_info['index']
        print(f"Default Input Device: [{default_input_idx}] {default_info['name']}")
    except Exception as e:
        print(f"No default input device found: {e}")

    for i in range(device_count):
        try:
            info = p.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                is_default = " (DEFAULT)" if i == default_input_idx else ""
                print(f" - Device [{i}]: {info['name']} (Channels: {info['maxInputChannels']}){is_default}")
        except Exception:
            continue
            
    if default_input_idx is None:
        print("\n[ERROR] No microphone available. Cannot run Voice Assistant.")
        p.terminate()
        return

    print("\nAttempting to open default microphone stream for 2 seconds...")
    try:
        # Open 2-second stream
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        print("Stream opened successfully. Listening...")
        
        frames = []
        for _ in range(0, int(16000 / 1024 * 2)):
            data = stream.read(1024)
            frames.append(data)
            
        print("Recorded 2 seconds of audio successfully!")
        stream.stop_stream()
        stream.close()
        print("Microphone diagnostic passed!")
        
    except Exception as e:
        print(f"\n[ERROR] Failed to open microphone stream: {e}")
        print("Please check Windows Privacy Settings -> Microphone Access is turned ON.")
        
    p.terminate()

if __name__ == "__main__":
    test_mic()
