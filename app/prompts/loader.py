import hashlib
from functools import lru_cache
from pathlib import Path
import yaml
from pydantic import BaseModel


class PromptArtifact(BaseModel):
    name: str
    version: str
    description: str
    system_prompt: str
    investigate_prompt: str
    verify_prompt: str
    sha256: str


PROMPT_FILES = {
    "v1": "v1_baseline.yaml",
    "v1_baseline": "v1_baseline.yaml",
    "baseline_single_pass": "v1_baseline.yaml",
    "v2": "v2_modifier_aware.yaml",
    "v2_modifier_aware": "v2_modifier_aware.yaml",
    "modifier_aware_multipass": "v2_modifier_aware.yaml",
    "phase0-v1": "v2_modifier_aware.yaml",
}


@lru_cache
def load_prompt(version: str = "v2_modifier_aware") -> PromptArtifact:
    filename = PROMPT_FILES.get(version, "v2_modifier_aware.yaml")
    path = Path(__file__).parent / filename
    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    data = yaml.safe_load(raw_bytes.decode("utf-8"))
    return PromptArtifact(
        name=data["name"],
        version=data["version"],
        description=data["description"],
        system_prompt=data["system_prompt"].strip(),
        investigate_prompt=data["investigate_prompt"].strip(),
        verify_prompt=data["verify_prompt"].strip(),
        sha256=digest[:12],
    )
