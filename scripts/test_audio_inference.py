import os

import librosa
import numpy as np
import torch

from app.inference.panns_classifier import (
    AUDIOSET_TO_SOUNDSENSE,
    CLIP_SAMPLES,
    SAMPLE_RATE,
    PANNsClassifier,
)

clf = PANNsClassifier('models/Cnn14_mAP=0.431.pth')

# Test files - add any path here
test_files = [
    os.path.expanduser('~/Downloads/knockdoor.mp3'),
]


def _debug_shapes(audio_path: str) -> None:
    """Print mel spectrogram shape and top 5 raw CNN14 scores before mapping."""
    # Load audio (same path as _infer_from_file)
    y, sr = librosa.load(audio_path, sr=None, mono=False)
    if y.ndim == 1:
        y = y[np.newaxis, :]
    waveform = torch.from_numpy(y.astype(np.float32))

    if sr != SAMPLE_RATE:
        import torchaudio
        waveform = torchaudio.functional.resample(waveform, orig_freq=sr, new_freq=SAMPLE_RATE)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    n = waveform.shape[1]
    if n < CLIP_SAMPLES:
        waveform = torch.nn.functional.pad(waveform, (0, CLIP_SAMPLES - n))
    else:
        waveform = waveform[:, :CLIP_SAMPLES]

    waveform = waveform.cpu()

    mel = clf._mel(waveform.cpu()).to(clf._device)      # (1, n_mels, time)
    mel = mel.squeeze(0).transpose(0, 1).unsqueeze(0)  # (1, time, mel_bins)
    print(f'  mel shape:    {tuple(mel.shape)}')

    with torch.no_grad():
        logits = clf._model(mel)                        # (1, 527)
    print(f'  logits shape: {tuple(logits.shape)}')

    scores = logits.squeeze(0).cpu().tolist()
    top5 = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:5]
    print('  top 5 raw scores:')
    for rank, (idx, score) in enumerate(top5, 1):
        label = clf._labels[idx] if idx < len(clf._labels) else f'class_{idx}'
        mapped = AUDIOSET_TO_SOUNDSENSE.get(label, '—')
        print(f'    {rank}. [{idx:>3}] {label:<45} {score:.4f}  →  {mapped}')


for path in test_files:
    if not os.path.exists(path):
        print(f'SKIP {path} — file not found')
        continue
    print(f'{os.path.basename(path)}:')
    _debug_shapes(path)
    event = clf.classify(audio_path=path)
    print(f'  mapped: {event.label} @ {event.confidence:.2f}')
