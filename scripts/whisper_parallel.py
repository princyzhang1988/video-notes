#!/usr/bin/env python3
"""Parallel Whisper transcription by splitting audio into chunks.

For M2 with tiny model (~72MB per instance), running 3-4 parallel
processes cuts transcription time by 2-3x.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed


def get_audio_duration(wav_path):
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', wav_path
    ], capture_output=True, text=True)
    info = json.loads(result.stdout)
    return float(info['format']['duration'])


def split_audio(wav_path, chunk_duration=180, overlap=10):
    """Split audio into overlapping chunks. Returns list of (start_time, chunk_path)."""
    total = get_audio_duration(wav_path)
    chunks = []
    start = 0
    i = 0
    while start < total:
        end = min(start + chunk_duration + overlap, total)
        chunk_path = f'/tmp/whisper_chunk_{i:03d}.wav'
        # Extract chunk with ffmpeg
        subprocess.run([
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', wav_path, '-ss', str(start), '-t', str(end - start),
            '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
            chunk_path
        ], check=True)
        chunks.append((start, chunk_path))
        start += chunk_duration
        i += 1
    return chunks


def transcribe_chunk(args):
    """Transcribe a single audio chunk with Whisper."""
    start_time, chunk_path, model, language = args
    output_dir = os.path.dirname(chunk_path)
    result = subprocess.run([
        'python3', '-m', 'whisper', chunk_path,
        '--model', model,
        '--language', language,
        '--output_dir', output_dir,
        '--output_format', 'json',
        '--fp16', 'False',
    ], capture_output=True, text=True, timeout=600)
    
    json_path = chunk_path.replace('.wav', '.json') + ''  # whisper replaces .wav with .json
    if not os.path.exists(json_path):
        # Also try alternate naming
        alt = chunk_path + '.json'
        if os.path.exists(alt):
            json_path = alt
        else:
            raise FileNotFoundError(f"No output found at {json_path} or {alt}. stderr: {result.stderr[-300:]}")
    
    with open(json_path) as f:
        data = json.load(f)
    
    # Adjust timestamps
    segments = []
    for seg in data['segments']:
        abs_start = start_time + seg['start']
        abs_end = start_time + seg['end']
        segments.append({
            't': f"{int(abs_start)//60:02d}:{int(abs_start)%60:02d}",
            's': round(abs_start, 1),
            'text': seg['text'].strip()
        })
    
    # Cleanup
    os.unlink(chunk_path)
    if os.path.exists(json_path):
        os.unlink(json_path)
    
    return segments


def merge_segments(all_segments, overlap=10):
    """Merge segments from parallel chunks, deduplicating overlap regions."""
    if not all_segments:
        return []
    
    # Flatten and sort by time
    flat = []
    for segs in all_segments:
        flat.extend(segs)
    flat.sort(key=lambda x: x['s'])
    
    # Deduplicate: remove segments that are too close to previous
    merged = []
    last_end = -999
    for seg in flat:
        # Only keep if it starts after the last segment's expected end
        # (allowing small overlap but removing true duplicates)
        if seg['s'] >= last_end - 1:  # 1s tolerance
            merged.append(seg)
            # Estimate end time from text length (~3 chars/s for Chinese)
            last_end = seg['s'] + max(len(seg['text']) / 3, 2)
    
    return merged


def main():
    parser = argparse.ArgumentParser(description='Parallel Whisper transcription')
    parser.add_argument('audio', help='Input WAV file (16kHz mono)')
    parser.add_argument('--model', default='tiny', help='Whisper model (default: tiny)')
    parser.add_argument('--language', default='Chinese', help='Language')
    parser.add_argument('--chunk-duration', type=int, default=180, help='Seconds per chunk (default: 180)')
    parser.add_argument('--parallel', type=int, default=3, help='Parallel workers (default: 3)')
    parser.add_argument('--output', default='/tmp/subs.json', help='Output JSON path')
    args = parser.parse_args()
    
    import time
    t0 = time.time()
    
    # Split
    chunks = split_audio(args.audio, args.chunk_duration, overlap=10)
    print(f"Split into {len(chunks)} chunks ({args.chunk_duration}s each, 10s overlap)")
    
    # Parallel transcribe
    tasks = [(start, path, args.model, args.language) for start, path in chunks]
    all_segments = []
    
    with ProcessPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(transcribe_chunk, t): t for t in tasks}
        for future in as_completed(futures):
            start, path, _, _ = futures[future]
            try:
                segs = future.result()
                all_segments.append(segs)
                print(f"  Chunk @{int(start)}s: {len(segs)} segments ✓")
            except Exception as e:
                print(f"  Chunk @{int(start)}s: FAILED ({e})")
    
    # Merge
    subs = merge_segments(all_segments)
    elapsed = time.time() - t0
    
    with open(args.output, 'w') as f:
        json.dump(subs, f, ensure_ascii=False)
    
    print(f"Total: {len(subs)} segments in {elapsed:.0f}s ({elapsed/get_audio_duration(args.audio):.1f}x realtime)")


if __name__ == '__main__':
    main()
