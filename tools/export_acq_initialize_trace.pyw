"""Read only the identified initialization trace; no NI/process operations."""
import datetime
import json
import os


def main():
    path = r"C:\ACQ_Python_Control_20261022_v8\runtime\initialize_2808_885e1150.jsonl"
    result = dict(utc=datetime.datetime.utcnow().isoformat() + "Z", path=path,
                  hardware_commands_sent=False, process_operations=False)
    try:
        with open(path, "rb") as stream:
            result["bytes"] = os.fstat(stream.fileno()).st_size
            if result["bytes"] > 2 * 1024 * 1024:
                stream.seek(-2 * 1024 * 1024, os.SEEK_END)
                stream.readline()
            lines = stream.read().decode("utf-8", "replace").splitlines()
        result["tail"] = []
        for line in lines[-50:]:
            try:
                result["tail"].append(json.loads(line))
            except ValueError:
                result["tail"].append(dict(incomplete_line=line[:500]))
    except Exception as error:
        result["error"] = type(error).__name__ + ": " + str(error)
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xp_initialize_trace_2808.json")
    with open(output, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
