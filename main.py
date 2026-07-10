from canvasapi import Canvas
from cryptography.fernet import Fernet, InvalidToken
import hashlib, base64
import os
import json
from rich.console import Console
import sys
import unidecode

def print_courses(courses: list, console: Console):
    for i, course in enumerate(courses):
        console.rule("", align='left')
        console.print(f"[bold cyan]{i+1}] [/bold cyan] {course}")

def limpiar(parte: str) -> str:
    parte = unidecode.unidecode(parte)
    prohibidos = '<>:"/\\|?* '
    nuevo = ""
    for letra in parte:
        if letra in prohibidos:
            if nuevo != "" and nuevo[-1] == "_":
                pass
            else:
                nuevo = nuevo + "_"
        else:
            nuevo = nuevo + letra
    nuevo = nuevo.rstrip(". ")
    if nuevo == "":
        nuevo = "_unnamed"
    return nuevo

def sync_courses(course_list, location, console):
    for course in course_list:
        console.print(f"\n[bold cyan]{course.name}[/bold cyan]")
        for folder in course.get_folders():
            if folder.full_name == "course files/_setup":
                continue
            course_name = limpiar(course.name)
            course_path = os.path.join(location, course_name)
            partes = [limpiar(parte) for parte in folder.full_name.split("/")]
            folder_path = os.path.join(course_path, *partes)    
            os.makedirs(folder_path, exist_ok=True)
            try:
                files = list(folder.get_files())
            except Exception as e:
                console.print(f"[bold red]Skipping {folder.full_name}: {e}[/bold red]")
                continue

            console.print(f"  [dim]{folder.full_name}[/dim] ({len(files)} files)")

            for file in files:
                if str(file.display_name).startswith("_"):
                    continue
                file_path = os.path.join(folder_path, limpiar(file.display_name))
                console.print(f"    Downloading {file.display_name}...", end="")
                try:
                    file.download(file_path)
                    console.print(" [bold green]done[/bold green]")
                except Exception as e:
                    console.print(f" [bold red]failed: {e}[/bold red]")


def unlock_token(config):
    console.print("Enter your password to decrypt the token")
    passw = console.input("[bold blue]> [/bold blue]", password=True)
    key = base64.urlsafe_b64encode(hashlib.sha256(passw.encode()).digest())
    cipher = Fernet(key)
    try:
        return cipher.decrypt(config["token"].encode()).decode()
    except InvalidToken:
        console.print("[bold red]Wrong password[/bold red]")
        sys.exit()


def connect(url, token):
    canvas = Canvas(url, token)
    try:
        user = Canvas.get_current_user(canvas)
        console.print(f"[bold green]Connected as {user.name}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Connection failed: {e}[/bold red]")
        sys.exit()
    return canvas


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        console.print("\n[bold yellow]Cancelled by user.[/bold yellow]")
        return
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


console = Console()
sys.excepthook = handle_exception

console.clear()
console.rule("[bold cyan]Canvas File Sync[/bold cyan]")
console.print("\nIf you want to continue and sync your canvas files press [1]", style="cyan")
console.print("If you want to sync the last selected courses press [2]", style="cyan")

confirm = console.input("[bold blue]> [/bold blue]")
if confirm not in ("1", "2"):
    sys.exit()

try:
    with open("config.json") as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    config = {}

if confirm == "2":
    if (config == {}) or ("included_course_ids" not in config):
        console.print("[bold red]No saved course selection found. Run option [1] first.[/bold red]")
        sys.exit()

    location = config["location"]
    canvas_url = config["url"]

    token = unlock_token(config)
    canvas = connect(canvas_url, token)

    course_list = []
    for cid in config["included_course_ids"]:
        try:
            course_list.append(canvas.get_course(cid))
        except Exception as e:
            console.print(f"[bold red]Skipping course {cid}: {e}[/bold red]")

    print_courses(course_list, console)

    console.clear()
    console.rule("[bold cyan]Syncing[/bold cyan]")
    sync_courses(course_list, location, console)
    console.rule("[bold green]Sync complete[/bold green]")
    sys.exit()

# confirm == "1" from here on
console.print("Do you want to reconfigure? (y/n)")
reconfigure = console.input("[bold blue]> [/bold blue]")

if (reconfigure=="y") or (config == {}):
    verify = False
    while(not verify):
        console.print("\nEnter the local files location for the sync")
        location = console.input("[bold blue]> [/bold blue]")
        verify = os.path.isdir(location)
        if (verify):
            console.print("[bold green]The file location is valid[/bold green]")
        else:
            console.print("[bold red]The file location is not valid[/bold red]")

    console.print("\nEnter your Canvas URL (e.g. school.instructure.com)")
    canvas_url = console.input("[bold blue]> [/bold blue]")
    canvas_url = "https://" + canvas_url

    console.print("\nEnter the acces token")
    token = console.input("[bold blue]> [/bold blue]")
    console.print("Enter a password for the encription")
    passw = console.input("[bold blue]> [/bold blue]", password=True)
    key = base64.urlsafe_b64encode(hashlib.sha256(passw.encode()).digest())
    cipher = Fernet(key)
    encrypted_token = cipher.encrypt(token.encode())

    config["location"] = location
    config["url"] = canvas_url
    config["token"] = encrypted_token.decode()

    with open("config.json", "w") as f:
        json.dump(config, f)

else:
    location = config["location"]
    canvas_url = config["url"]
    token = unlock_token(config)

canvas = connect(canvas_url, token)

courses = Canvas.get_courses(canvas)
course_list = list(courses)

print_courses(course_list, console)

console.print("\nEnter numbers to include (comma separated), or press enter to skip")
to_include = console.input("[bold blue]> [/bold blue]")

if to_include != "":
    numbers = to_include.split(',')
    new_list = []
    for n in numbers:
        index = int(n) - 1
        new_list.append(course_list[index])
    course_list = new_list

print_courses(course_list, console)

config["included_course_ids"] = [course.id for course in course_list]
with open("config.json", "w") as f:
    json.dump(config, f)

console.clear()
console.rule("[bold cyan]Syncing[/bold cyan]")
sync_courses(course_list, location, console)
console.rule("[bold green]Sync complete[/bold green]")
