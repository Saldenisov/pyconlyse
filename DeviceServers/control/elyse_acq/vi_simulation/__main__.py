"""Print one offline initializer trace. This is not the Acquisition main loop."""

import argparse
import json

from . import (
    NO_ERROR,
    SampleClockInputs,
    ScriptedBoundary,
    initialize_dio96,
    initialize_ni6071e,
    initialize_ni6220,
    initialize_ni6602,
    initialize_ni6703,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "vi", choices=("dio96", "ni6071e", "ni6220", "ni6602", "ni6703")
    )
    parser.add_argument("--rate-hz", type=float)
    parser.add_argument("--samples", type=int)
    parser.add_argument("--trigger-c1")
    parser.add_argument("--trigger-c2")
    args = parser.parse_args(argv)
    inputs = {"error_in": NO_ERROR}
    if args.vi in ("ni6071e", "ni6220"):
        if args.rate_hz is None or args.samples is None:
            parser.error("AI traces require explicit --rate-hz and --samples")
        try:
            inputs["clock"] = SampleClockInputs(args.rate_hz, args.samples)
        except ValueError as error:
            parser.error(str(error))
    elif args.rate_hz is not None or args.samples is not None:
        parser.error("sample clock arguments apply only to AI traces")
    if args.vi == "ni6071e":
        if args.trigger_c1 is None or args.trigger_c2 is None:
            parser.error("NI6071E requires explicit --trigger-c1 and --trigger-c2")
        inputs.update(trigger_c1=args.trigger_c1, trigger_c2=args.trigger_c2)
    elif args.trigger_c1 is not None or args.trigger_c2 is not None:
        parser.error("caller trigger arguments apply only to NI6071E")
    initializers = {
        "dio96": initialize_dio96,
        "ni6071e": initialize_ni6071e,
        "ni6220": initialize_ni6220,
        "ni6602": initialize_ni6602,
        "ni6703": initialize_ni6703,
    }
    boundary = ScriptedBoundary()
    result = initializers[args.vi](boundary, **inputs)
    boundary.assert_all_fixtures_used()
    print(json.dumps(result.to_dict(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
