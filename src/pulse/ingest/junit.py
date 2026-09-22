"""Ingest JUnit XML reports from a directory.

Each XML file is one CI run. Filenames become run IDs (sorted
lexicographically). Every testcase becomes a TestRun.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from pulse.models import TestRun, TestStatus


def ingest_directory(directory):
    """Read every .xml file in a directory. Returns list of TestRun.

    Files are sorted by filename. run_id = filename stem. commit_sha is
    extracted from the filename if it looks like 'run-<sha>.xml', else
    empty.
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError("reports directory not found: " + str(directory))

    files = sorted(directory.glob("*.xml"))
    if not files:
        raise ValueError("no .xml files found in " + str(directory))

    all_runs = []
    for xml_file in files:
        run_id = xml_file.stem
        commit_sha = ""
        if run_id.startswith("run-"):
            commit_sha = run_id[4:]
        all_runs.extend(_parse_file(xml_file, run_id, commit_sha))
    return all_runs


def _parse_file(path, run_id, commit_sha):
    tree = ET.parse(path)
    root = tree.getroot()

    if root.tag == "testsuites":
        suites = root.findall(".//testsuite")
    else:
        suites = [root]

    runs = []
    for suite in suites:
        for case in suite.findall("testcase"):
            status = TestStatus.PASSED.value
            error_message = ""

            fail_el = case.find("failure")
            if fail_el is None:
                fail_el = case.find("error")
            if fail_el is not None:
                status = TestStatus.FAILED.value
                error_message = (fail_el.get("message", "") or "")[:300]

            skip_el = case.find("skipped")
            if skip_el is not None:
                status = TestStatus.SKIPPED.value

            name = case.get("name", "")
            classname = case.get("classname", "")
            test_id = classname + "::" + name if classname else name

            duration = 0.0
            time_attr = case.get("time")
            if time_attr:
                try:
                    duration = float(time_attr) * 1000.0
                except ValueError:
                    pass

            runs.append(TestRun(
                test_id=test_id,
                name=name,
                file=classname,
                status=status,
                duration_ms=duration,
                run_id=run_id,
                commit_sha=commit_sha,
                error_message=error_message,
            ))
    return runs


def build_histories(runs):
    """Group TestRun objects by test_id into TestHistory objects."""
    from pulse.models import TestHistory

    by_id = {}
    for r in runs:
        if r.test_id not in by_id:
            by_id[r.test_id] = TestHistory(
                test_id=r.test_id,
                name=r.name,
                file=r.file,
            )
        by_id[r.test_id].runs.append(r)

    # Sort runs by run_id for consistent transition counting
    for h in by_id.values():
        h.runs.sort(key=lambda r: r.run_id)

    return list(by_id.values())
