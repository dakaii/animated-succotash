"""Bundle vm/ files into a startup-script extract step for GCP metadata."""

import base64
import io
import tarfile
from pathlib import Path

VM_DIR = Path(__file__).parent.parent / "vm"
BUNDLE_ROOT = "/opt/hermes-bundle"
# startup.sh is the metadata entrypoint template, not part of the tarball.
SKIP_IN_BUNDLE = {"startup.sh"}


def build_extract_script() -> str:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path in sorted(VM_DIR.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(VM_DIR).as_posix()
            if relative in SKIP_IN_BUNDLE:
                continue
            archive.add(path, arcname=relative)

    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"""\
mkdir -p {BUNDLE_ROOT}
echo '{payload}' | base64 -d | tar -xzf - -C {BUNDLE_ROOT}
chmod +x {BUNDLE_ROOT}/bootstrap.sh
find {BUNDLE_ROOT}/lib -name '*.sh' -exec chmod +x {{}} \\;
"""


def build_startup_script(
    project_id: str,
    model: str,
    ingress_mode: str,
    public_hostname: str,
    telegram_webhook: bool,
) -> str:
    template = (VM_DIR / "startup.sh").read_text()
    template = template.replace("__PROJECT_ID__", project_id)
    template = template.replace("__MODEL__", model)
    template = template.replace("__INGRESS_MODE__", ingress_mode)
    template = template.replace("__PUBLIC_HOSTNAME__", public_hostname)
    template = template.replace(
        "__TELEGRAM_WEBHOOK__", "true" if telegram_webhook else "false"
    )
    return build_extract_script() + "\n" + template
