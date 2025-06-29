#!/usr/bin/env python3
import os
import sys
from huggingface_hub import hf_hub_download
import argparse

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_links_file(links_file):
    links = []
    with open(links_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and "]" in line:
                tag_end = line.index("]")
                tag = line[1:tag_end]
                url = line[tag_end + 1:].strip().split()[0]
                links.append((tag, url))
    return links

def parse_hf_url(url):
    parts = url.split("/")
    try:
        idx = parts.index("huggingface.co")
    except ValueError:
        raise ValueError(f"Некорректный URL: {url}")
    repo_id = parts[idx+1] + "/" + parts[idx+2]
    revision = parts[idx+4]
    filename = "/".join(parts[idx+5:])  # исправлено, чтобы учитывать поддиректории
    return repo_id, filename, revision

def main():
    parser = argparse.ArgumentParser(description="Загрузка моделей с Hugging Face через huggingface_hub")
    parser.add_argument("--manual", action="store_true", help="Ручной режим выбора моделей")
    parser.add_argument("--links-file", type=str, default="model_links.txt", help="Файл со ссылками")
    parser.add_argument("--token", type=str, default=os.getenv("HF_TOKEN"), help="Токен Hugging Face")
    args = parser.parse_args()

    if not args.token:
        print("Ошибка: не задан токен Hugging Face. Установите HF_TOKEN или передайте --token.")
        sys.exit(1)

    links = parse_links_file(args.links_file)
    to_download = []

    if args.manual:
        print("Ручной режим выбора моделей.")
        for tag, url in links:
            filename = url.split("/")[-1]
            if tag == "clip":
                filename = "clip_l.safetensors"
            while True:
                answer = input(f"Скачать {tag} - {filename}? (y/n): ").strip().lower()
                if answer in ("y", "n"):
                    break
                print("Пожалуйста, введите 'y' или 'n'.")
            if answer == "y":
                to_download.append((tag, url))
    else:
        print("Автоматический режим: скачиваем все модели.")
        to_download = links

    for tag, url in to_download:
        repo_id, filename, revision = parse_hf_url(url)
        folder = os.path.join(PROJECT_DIR, "comfyui", "models", tag)
        os.makedirs(folder, exist_ok=True)

        local_filename = "clip_l.safetensors" if tag == "clip" else os.path.basename(filename)
        local_path = os.path.join(folder, local_filename)

        print(f"Скачиваем {repo_id}/{filename} (revision={revision}) → {local_path}")
        try:
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                token=args.token,
                local_dir=folder,
                force_download=False,
            )
            # Переименование если нужно
            if downloaded_path != local_path:
                os.replace(downloaded_path, local_path)
                original_dir = os.path.dirname(downloaded_path)
                try:
                    os.rmdir(original_dir)  # удалит только если папка пустая
                except OSError:
                    pass
            print(f"Скачано: {local_path}")
        except Exception as e:
            print(f"Ошибка при скачивании {url}: {e}")

if __name__ == "__main__":
    main()
