from ai_helper.llm import GrokAdapter


def main() -> None:
    adapter = GrokAdapter(adapter_path=None, mock=True)
    calls = adapter.request_tool_calls("move cube up", {"objects": []}, use_mock=True)

    assert calls
    assert calls[0].name == "transform_object"


if __name__ == "__main__":
    main()
