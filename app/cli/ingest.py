import argparse
import json

from app.config import get_settings
from app.rag.ingest import ingest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index only the three verified active PDFs")
    parser.add_argument("--re-embed-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(ingest(get_settings(), args.re_embed_only), indent=2))
