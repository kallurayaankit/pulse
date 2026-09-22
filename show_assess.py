from pulse.ingest import ingest_directory, build_histories
from pulse.analyze import assess_all

runs = ingest_directory("examples/reports")
histories = build_histories(runs)
assessments, health = assess_all(histories, runs)

print("=== Suite health ===")
for k, v in health.to_dict().items():
    if isinstance(v, float):
        print(f"  {k}: {v:.2f}")
    else:
        print(f"  {k}: {v}")
print()

print("=== Assessments (ranked) ===")
for a in assessments:
    flags = []
    if a.is_flaky: flags.append("FLAKY")
    if a.is_duplicate: flags.append("DUPLICATE")
    if a.is_low_value: flags.append("LOW_VALUE")
    flag_str = " ".join(flags) if flags else "OK"
    print(f"  [{a.recommendation:12s}] {a.name:35s} {flag_str}")
    print(f"      {a.reason}")