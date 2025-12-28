import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_helper.llm import GrokAdapter, get_tool_schema  # noqa: E402


def _download_test_image(url: str) -> Path:
    path = Path(tempfile.gettempdir()) / "ai_helper_vision_test.jpg"
    urllib.request.urlretrieve(url, path)
    return path


def main() -> int:
    if not os.getenv("XAI_API_KEY"):
        print("XAI_API_KEY missing; set env to run the vision smoke test.")
        return 2

    adapter_path = (ROOT / ".." / ".." / "ML" / "agents_assembly" / "llm_interfaces" / "grok.py").resolve()
    if not adapter_path.exists():
        print(f"Adapter not found: {adapter_path}")
        return 2

    image_input = os.getenv("GROK_VISION_IMAGE_URL")
    use_data_url = os.getenv("GROK_VISION_USE_DATA_URL", "").lower() in {"1", "true", "yes"}
    default_url = "https://picsum.photos/seed/aihelper/128"
    if use_data_url:
        test_url = image_input or default_url
        print(f"Using data URL from downloaded image: {test_url}")
        image_path = _download_test_image(test_url)
    elif image_input:
        image_path = image_input
    else:
        print(f"GROK_VISION_IMAGE_URL not set; using HTTPS URL: {default_url}")
        image_path = default_url
    prompt = "Create a simple 2D sketch from the image. Return tool_calls only."
    selection = {"objects": []}

    adapter = GrokAdapter(adapter_path=str(adapter_path), mock=False)
    try:
        tool_calls = adapter.request_tool_calls(
            prompt,
            selection,
            tools=get_tool_schema(),
            image_path=str(image_path),
            image_notes="Simple vision smoke test.",
        )
    except Exception as exc:
        print(f"Vision request failed: {exc}")
        return 1

    names = ", ".join(call.name for call in tool_calls) if tool_calls else "none"
    print(f"Tool calls: {len(tool_calls)}")
    print(f"Names: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
