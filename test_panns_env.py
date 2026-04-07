import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import torch
from panns_inference import AudioTagging
import librosa

device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Using device: {device}")

tagger = AudioTagging(checkpoint_path=None, device=device)

#audio, _ = librosa.load("smoke-alarm.mp3", sr=32000, mono=True)
audio, _ = librosa.load("test_audio/smoke-alarm.mp3", sr=32000, mono=True)
audio = audio[None, :]

clipwise, embedding = tagger.inference(audio)
print(f"Output shape: {clipwise.shape}")  # (1, 527)
print(f"Embedding shape: {embedding.shape}")  # (1, 2048)

top5 = clipwise[0].argsort()[-5:][::-1]
for i in top5:
    print(f"  {tagger.labels[i]:45s} {clipwise[0][i]:.3f}")