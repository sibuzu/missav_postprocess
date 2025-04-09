import faster_whisper
import os
import argparse
import subprocess

def convert_to_srt(segments, output_path):
    """將 fast-whisper 的轉錄結果轉換為 SRT 字幕格式。"""
    srt_content = ""
    for i, segment in enumerate(segments):
        start_time = segment.start
        end_time = segment.end
        text = segment.text.strip()

        # 將時間轉換為 SRT 格式 (HH:MM:SS,ms)
        def format_time(seconds):
            milliseconds = int(seconds * 1000) % 1000
            seconds = int(seconds) % 60
            minutes = int(seconds / 60) % 60
            hours = int(seconds / 3600)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        srt_content += f"{i+1}\n"
        srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
        srt_content += f"{text}\n\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    print(f"字幕已儲存至: {output_path}")

def extract_audio(video_path, audio_output_path):
    """使用 ffmpeg 從影片檔案中提取音訊。"""
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_output_path],
            check=True,
            capture_output=True
        )
        print(f"音訊已提取至: {audio_output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"提取音訊時發生錯誤: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("找不到 ffmpeg，請確保已安裝並添加到系統路徑。")
        return False

def transcribe_audio(audio_path, model_name, output_srt_path, language=None):
    """使用 fast-whisper 轉錄音訊並保存為 SRT 檔案。"""
    model = faster_whisper.WhisperModel(model_name)
    try:
        segments, info = model.transcribe(audio_path, beam_size=5, language=language)
        print(f"偵測到的語言：'{info.language}'，可信度：{info.language_probability:.2f}")
        convert_to_srt(segments, output_srt_path)
        return True
    except Exception as e:
        print(f"轉錄音訊時發生錯誤: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="將音訊或影片檔案轉錄為同名的 SRT 字幕檔案。")
    parser.add_argument("input_file", help="輸入的音訊檔案 (.wav, .mp3 等) 或影片檔案 (.mp4, .mkv 等)。")
    parser.add_argument("-m", "--model", default="base", help="Whisper 模型大小 (tiny, base, small, medium, large-v1, large-v2, large-v3)。預設: base")
    parser.add_argument("-l", "--language", default=None, help="指定的語言代碼 (例如: en, zh)。如果未指定，將嘗試自動偵測。")
    args = parser.parse_args()

    input_file = args.input_file
    model_name = args.model
    language = args.language

    base, ext = os.path.splitext(input_file)
    output_srt_path = f"{base}.srt"
    temp_audio_path = f"{base}_temp_audio.wav"

    if ext.lower() in [".mp4", ".mkv", ".mov", ".avi"]:
        if extract_audio(input_file, temp_audio_path):
            transcribe_audio(temp_audio_path, model_name, output_srt_path, language)
            os.remove(temp_audio_path)  # 清理臨時音訊檔案
    elif ext.lower() in [".wav", ".mp3", ".ogg", ".flac"]:
        transcribe_audio(input_file, model_name, output_srt_path, language)
    else:
        print(f"不支援的檔案格式: {ext}")

if __name__ == "__main__":
    main()