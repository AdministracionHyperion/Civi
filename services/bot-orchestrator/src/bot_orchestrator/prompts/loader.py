from __future__ import annotations

from importlib.resources import files

BASE_PROMPT_FILES = (
    "identity.md",
    "consent.md",
    "response_policy.md",
    "tools_policy.md",
)

FLOW_PROMPT_FILES = (
    "flows/soat.md",
    "flows/tecnomecanica.md",
    "flows/licencia.md",
    "flows/curso_multa.md",
    "flows/agenda.md",
)


def build_system_prompt(*, include_flows: bool = True) -> str:
    prompt_files = list(BASE_PROMPT_FILES)
    if include_flows:
        prompt_files.extend(FLOW_PROMPT_FILES)

    sections = []
    for prompt_file in prompt_files:
        content = load_prompt_part(prompt_file)
        sections.append(f"<!-- {prompt_file} -->\n{content}")
    return "\n\n".join(sections).strip()


def load_prompt_part(prompt_file: str) -> str:
    root = files("bot_orchestrator.prompts")
    resource = root.joinpath(*prompt_file.split("/"))
    if not resource.is_file():
        raise FileNotFoundError(f"prompt part not found: {prompt_file}")
    return resource.read_text(encoding="utf-8").strip()
