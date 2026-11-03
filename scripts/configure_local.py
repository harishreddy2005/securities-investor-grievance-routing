"""Create/extend .env without replacing existing values or printing credentials."""
from pathlib import Path
import secrets


def configure(root=Path.cwd()):
    path=root/".env"
    text=path.read_text(encoding="utf-8-sig") if path.exists() else (root/".env.example").read_text(encoding="utf-8")
    keys={line.split("=",1)[0]:line.split("=",1)[1] for line in text.splitlines() if "=" in line and not line.lstrip().startswith("#")}
    additions=[]
    for key,value in {"GRAFANA_ADMIN_USER":"admin","GRAFANA_ADMIN_PASSWORD":secrets.token_urlsafe(24)}.items():
        if not keys.get(key):
            text="\n".join(line for line in text.splitlines() if not line.startswith(key+"="))
            additions.append(key+"="+value)
    path.write_text(text.rstrip()+"\n"+"\n".join(additions)+("\n" if additions else ""),encoding="utf-8")
    print("Local .env ready. Grafana credentials are stored there; existing settings preserved.")


if __name__ == "__main__":
    configure()
