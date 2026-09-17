import subprocess
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ============== 配置 ==============

INPUT_VIDEO = "-"          # 输入视频
OUTPUT_DIR = "-"       # 固定输出目录

INTERVAL = 1
WEBP_QUALITY = 82
COMPRESSION_LEVEL = 2
MAX_WIDTH = 1920

WORKERS = 8  # 同时跑几个 FFmpeg，建议 4~8

# =================================


def get_duration():
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            INPUT_VIDEO,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def process_chunk(start_frame, frame_count):
    start_time = start_frame * INTERVAL

    filters = [f"fps=1/{INTERVAL}"]

    if MAX_WIDTH > 0:
        filters.append(
            f"scale=min({MAX_WIDTH}\\,iw):-2"
        )

    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-y",

        # Apple Silicon 硬件解码
        "-hwaccel", "videotoolbox",

        # 从该分段直接开始
        "-ss", str(start_time),
        "-i", INPUT_VIDEO,

        "-vf", ",".join(filters),

        # 只处理这个 worker 负责的帧数
        "-frames:v", str(frame_count),

        "-c:v", "libwebp",
        "-quality", str(WEBP_QUALITY),
        "-compression_level", str(COMPRESSION_LEVEL),
        "-preset", "picture",

        # 直接使用全局编号，不需要最后重命名
        "-start_number", str(start_frame + 1),

        str(Path(OUTPUT_DIR) / "frame_%06d.webp"),
    ]

    subprocess.run(cmd, check=True)


def main():
    output = Path(OUTPUT_DIR)
    output.mkdir(parents=True, exist_ok=True)

    # 删除之前生成的帧，防止旧图片残留
    for file in output.glob("frame_*.webp"):
        file.unlink()

    duration = get_duration()
    total_frames = math.ceil(duration / INTERVAL)

    workers = min(WORKERS, total_frames)
    chunk_size = math.ceil(total_frames / workers)

    tasks = []

    for i in range(workers):
        start = i * chunk_size

        if start >= total_frames:
            break

        count = min(
            chunk_size,
            total_frames - start
        )

        tasks.append((start, count))

    print(
        f"{duration:.1f}s | "
        f"{total_frames} frames | "
        f"{len(tasks)} workers"
    )

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(
                process_chunk,
                start,
                count
            )
            for start, count in tasks
        ]

        for future in futures:
            future.result()

    print("完成")


if __name__ == "__main__":
    main()
