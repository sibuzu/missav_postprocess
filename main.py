import os
import glob
import logging
import sys
from datetime import datetime
from faster_whisper import WhisperModel
import subprocess
from myai import get_summary

# Set up base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) + "/../"

# Create log directory if it doesn't exist
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
os.makedirs(LOG_DIR, exist_ok=True)

# Set up logging
log_file = os.path.join(LOG_DIR, f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Create custom StreamHandler with UTF-8 encoding
class UTFStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.buffer.write(f"{msg}{self.terminator}".encode('utf-8'))
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        UTFStreamHandler(sys.stdout)
    ]
)

def extract_audio(video_path, audio_output_path):
    """使用 ffmpeg 從影片檔案中提取音訊"""
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", 
            "-ac", "1", audio_output_path],
            check=True,
            capture_output=True
        )
        logging.info(f"音訊已提取至: {audio_output_path}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"提取音訊時發生錯誤: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        logging.error("找不到 ffmpeg，請確保已安裝並添加到系統路徑。")
        return False

def convert_to_srt(segments, output_path):
    """將 fast-whisper 的轉錄結果轉換為 SRT 字幕格式"""
    def format_time(t):
        milliseconds = int(t * 1000) % 1000
        seconds = int(t) % 60
        minutes = int(t) // 60 % 60
        hours = int(t) // 3600
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments):
            f.write(f"{i+1}\n")
            f.write(f"{format_time(segment.start)} --> {format_time(segment.end)}\n")
            f.write(f"{segment.text.strip()}\n\n")
            logging.info(f"{format_time(segment.start)} --> {format_time(segment.end)} {segment.text.strip()}")
    
    logging.info(f"字幕已儲存至: {output_path}")
    return True

def do_srt(video_path):
    # 1. 檢查同名 srt 是否存在
    srt_path = os.path.splitext(video_path)[0] + ".srt"
    if os.path.exists(srt_path):
        # 2. 若存在則跳過
        logging.info(f"字幕檔已存在，跳過處理: {srt_path}")
        return

    # 3. 用 ffmpeg 將 mp4 轉為 temp.wav
    temp_wav = os.path.splitext(video_path)[0] + ".temp.wav"
    temp_srt = os.path.splitext(video_path)[0] + ".test.srt"
    
    try:
        if not extract_audio(video_path, temp_wav):
            return

        # 4. 用 faster-whisper 將 temp.wav 轉為 test.srt
        model = WhisperModel("large-v3", device="cuda", compute_type="float32")
        segments, info = model.transcribe(temp_wav, beam_size=5, language="ja")
        
        logging.info(f"偵測到的語言：'{info.language}'，可信度：{info.language_probability:.2f}")
        
        if convert_to_srt(segments, temp_srt):
            # 5. 若成功，rename test.srt 為同名 srt, unlink temp.wav
            os.rename(temp_srt, srt_path)
            os.unlink(temp_wav)
            logging.info(f"成功完成字幕轉換: {srt_path}")
    except Exception as e:
        logging.error(f"處理檔案時發生錯誤: {e}")
    finally:
        # 清理臨時檔案
        logging.info(f"清理臨時檔案: {temp_wav}, {temp_srt}")
        if os.path.exists(temp_wav):
            os.unlink(temp_wav)
        if os.path.exists(temp_srt):
            os.unlink(temp_srt)
        logging.info("清理完成")

def do_summary(video_path):
    logging.info(f"Processing summary for: {video_path}")
    # 1. 檢查 srt file 是否存在
    srt_path = os.path.splitext(video_path)[0] + ".srt"
    if not os.path.exists(srt_path):
        logging.info(f"找不到字幕檔，跳過摘要生成: {srt_path}")
        return

    # 2. 檢查 summary file 是否存在
    summary_path = os.path.splitext(video_path)[0] + "_summary.txt"
    if os.path.exists(summary_path):
        logging.info(f"摘要檔已存在，跳過處理: {summary_path}")
        return

    try:
        # 讀取 SRT 文件內容
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 3. 將內容分割成 64K 的區塊
        MAX_BLOCK_SIZE = 64 * 1024  # 64KB
        blocks = []
        current_block = []
        current_size = 0

        for line in content.split('\n'):
            # 若是 line 全部只有空白、數字、.:,->, 則跳過
            line = line.strip()
            if all(c in ' 0123456789.:,->-' for c in line):
                continue

            line_size = len(line.encode('utf-8'))
            
            if current_size + line_size > MAX_BLOCK_SIZE and current_block:
                blocks.append('\n'.join(current_block))
                current_block = [line]
                current_size = line_size
            else:
                current_block.append(line)
                current_size += line_size

        if current_block:
            blocks.append('\n'.join(current_block))

        # 4. 對每個區塊調用 get_summary
        summaries = []
        for i, block in enumerate(blocks):
            logging.info(f"處理區塊 {i+1}/{len(blocks)}")
            summary = get_summary(block)
            print(summary)
            summaries.append(summary)

        # 5. 合併摘要並儲存
        final_summary = '\n\n'.join(summaries)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(final_summary)
        
        logging.info(f"摘要已儲存至: {summary_path}")

    except Exception as e:
        logging.error(f"生成摘要時發生錯誤: {e}")

def main():
    logging.info(f"Base directory: {BASE_DIR}")
    mp4_files = glob.glob(os.path.join(BASE_DIR, "**/*.mp4"), recursive=True)
    for (i, file) in enumerate(mp4_files):
        try:
            logging.info(f"Processing file {i+1}/{len(mp4_files)}: {file}")
            do_srt(file)
            # do_summary(file)
            logging.info(f"Finished processing file {i+1}/{len(mp4_files)}: {file}")
        except Exception as e:
            logging.error(f"處理檔案時發生錯誤: {file} - {e}")
            continue  # 繼續處理下一個檔案

if __name__ == "__main__":
    main()
