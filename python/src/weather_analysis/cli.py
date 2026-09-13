"""Command-line handoff for publication, custom analyses and evidence exports."""

import argparse
import json
from pathlib import Path

from .evidence import export_evidence
from .service import AnalysisService
from .storage import DatasetStore, publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/platform"))
    sub = parser.add_subparsers(dest="command", required=True)
    publication = sub.add_parser("publish")
    publication.add_argument("--data-root", type=Path, default=Path("data"))
    publication.add_argument("--version", required=True)
    job = sub.add_parser("run")
    job.add_argument("spec", type=Path)
    job.add_argument("--version")
    job.add_argument("--no-cache", action="store_true")
    sub.add_parser("overview")
    sub.add_parser("history")
    evidence = sub.add_parser("evidence")
    evidence.add_argument("--version")
    evidence.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "publish":
        print(json.dumps(publish(args.data_root, args.root, args.version), indent=2))
    elif args.command == "overview":
        print(json.dumps(DatasetStore(args.root).get_overview(), indent=2))
    elif args.command == "history":
        print(json.dumps(AnalysisService(args.root).list_jobs(), indent=2))
    elif args.command == "run":
        service = AnalysisService(
            args.root, args.version, ttl_seconds=0 if args.no_cache else 86400
        )
        job_id = service.submit_job(json.loads(args.spec.read_text()))
        status = service.get_job_status(job_id)
        print(json.dumps(status, indent=2))
        if status["status"] != "completed":
            raise SystemExit(1)
        print(service.load_job_result(job_id).to_string(index=False))
    elif args.command == "evidence":
        store = DatasetStore(args.root, args.version)
        print(export_evidence(store, args.output or args.root / "evidence" / store.version))


if __name__ == "__main__":
    main()
