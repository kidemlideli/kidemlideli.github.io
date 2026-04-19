#!/usr/bin/env python3
import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parent
BLOG_DIR = REPO_ROOT / "content" / "blog"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_github_token() -> str | None:
    if token := os.environ.get("GITHUB_TOKEN"):
        return token
    env_values = load_env_file(REPO_ROOT / ".env")
    return env_values.get("GITHUB_TOKEN")


def get_url_with_token(remote: str, token: str) -> str:
    remote_url = run_git("remote", "get-url", remote, capture_output=True)
    if not remote_url.startswith("https://"):
        raise SystemExit("Uzak origin URL'si https:// ile başlamalı.")
    return re.sub(r"^https://(?:[^@]+@)?", f"https://{token}@", remote_url)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9ğüşöçıİĞÜŞÖÇ]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text


def run_git(*args, capture_output=False):
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True,
                            capture_output=capture_output)
    if capture_output:
        return result.stdout.strip()
    if result.returncode != 0:
        raise SystemExit(f"Git komutu başarısız: git {' '.join(args)}")


def ensure_git_repo():
    if not (REPO_ROOT / ".git").exists():
        raise SystemExit("Bu dizin bir git deposu değil. önce `git init` yapmalısın.")


def init_repo(remote: str | None, name: str, email: str):
    if (REPO_ROOT / ".git").exists():
        print("Zaten git deposu mevcut.")
    else:
        run_git("init")
        print("Git deposu başlatıldı.")
    run_git("config", "user.name", name)
    run_git("config", "user.email", email)
    print(f"Yerel git kimliği ayarlandı: {name} <{email}>")
    if remote:
        remotes = run_git("remote", "-v", capture_output=True)
        if "origin" in remotes:
            print("origin zaten var, değiştirmek için önce silmelisin.")
        else:
            run_git("remote", "add", "origin", remote)
            print(f"origin uzaktan bağlantısı eklendi: {remote}")


def new_post(title: str, description: str | None, categories: list[str], tags: list[str], draft: bool):
    date = datetime.now().date()
    slug = slugify(title)
    filename = f"{slug}.md"
    path = BLOG_DIR / filename
    if path.exists():
        raise SystemExit(f"Bu slug zaten var: {filename}")
    if not BLOG_DIR.exists():
        BLOG_DIR.mkdir(parents=True, exist_ok=True)
    frontmatter = ["+++",
                   f'title = "{title}"',
                   f'date = {date}',
                   f'description = "{description or title}"',
                   f'categories = {categories if categories else []}',
                   f'tags = {tags if tags else []}',
                   f'image = ""',
                   f'draft = {str(draft).lower()}',
                   "+""+",
                   "",
                   "Yazının girişini buraya yazın.",
                   ""]
    path.write_text("\n".join(frontmatter), encoding="utf-8")
    print(f"Yeni gönderi oluşturuldu: {path.relative_to(REPO_ROOT)}")
    return path


def commit_changes(message: str):
    ensure_git_repo()
    run_git("add", ".")
    result = subprocess.run(["git", "commit", "-m", message], cwd=REPO_ROOT, text=True,
                            capture_output=True)
    if result.returncode == 0:
        print(f"Commit yapıldı: {message}")
    elif "nothing to commit" in result.stdout.lower() or "nothing to commit" in result.stderr.lower():
        print("Commit yapılacak değişiklik yok. Sadece push yapılacak.")
    else:
        raise SystemExit(f"Git komutu başarısız: git commit -m {message}\n{result.stderr.strip()}")


def push_changes(branch: str, remote: str, token: str | None = None):
    ensure_git_repo()
    if token:
        remote_target = get_url_with_token(remote, token)
        run_git("push", "-u", remote_target, branch)
        print(f"Değişiklikler gönderildi: {remote}/{branch} (token kullanıldı)")
    else:
        run_git("push", "-u", remote, branch)
        print(f"Değişiklikler gönderildi: {remote}/{branch}")


def status():
    ensure_git_repo()
    print(run_git("status"))


def main():
    parser = argparse.ArgumentParser(description="Kıdemli Deli için hızlı yayın scripti")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="Repo başlat ve anonim kullanıcı ayarla")
    p_init.add_argument("--remote", help="Origin uzak adresi")
    p_init.add_argument("--name", default="Anonim", help="Git kullanıcı adı")
    p_init.add_argument("--email", default="anon@ornek.com", help="Git kullanıcı email")

    p_new = subparsers.add_parser("new", help="Yeni bir blog yazısı oluştur")
    p_new.add_argument("title", help="Yazı başlığı")
    p_new.add_argument("--description", default=None, help="Yazı açıklaması")
    p_new.add_argument("--categories", default="", help="Kategoriler (virgülle ayrılmış)")
    p_new.add_argument("--tags", default="", help="Etiketler (virgülle ayrılmış)")
    p_new.add_argument("--draft", action="store_true", help="Taslak yap")

    p_commit = subparsers.add_parser("commit", help="Tüm değişiklikleri commit et")
    p_commit.add_argument("message", help="Commit mesajı")

    p_push = subparsers.add_parser("push", help="Değişiklikleri origin'e gönder")
    p_push.add_argument("--branch", default="main", help="Branch adı")
    p_push.add_argument("--remote", default="origin", help="Uzak repo adı")
    p_push.add_argument("--token", default=None, help="GitHub PAT (token)")

    p_pub = subparsers.add_parser("publish", help="Commit ve push işlemini tek adımda yap")
    p_pub.add_argument("message", help="Commit mesajı")
    p_pub.add_argument("--branch", default="main", help="Branch adı")
    p_pub.add_argument("--remote", default="origin", help="Uzak repo adı")
    p_pub.add_argument("--token", default=None, help="GitHub PAT (token)")

    p_status = subparsers.add_parser("status", help="Git durumunu göster")

    args = parser.parse_args()

    if args.command == "init":
        init_repo(args.remote, args.name, args.email)
    elif args.command == "new":
        categories = [c.strip() for c in args.categories.split(",") if c.strip()]
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        new_post(args.title, args.description, categories, tags, args.draft)
    elif args.command == "commit":
        commit_changes(args.message)
    elif args.command == "push":
        push_changes(args.branch, args.remote, args.token)
    elif args.command == "publish":
        commit_changes(args.message)
        push_changes(args.branch, args.remote, args.token or get_github_token())
    elif args.command == "status":
        status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
