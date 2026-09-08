import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "capacity_report", Path(__file__).parents[1] / "capacity-report.py"
)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class CapacityReportTests(unittest.TestCase):
    def test_missing_data_is_not_zero_load(self):
        self.assertEqual(report.summarize([], 10), {"samples": 0, "coverage_percent": 0.0})

    def test_nonfinite_samples_reduce_coverage(self):
        stats = report.summarize([[0, "NaN"], [1, "+Inf"], [2, "42"]], 3)
        self.assertEqual(stats["samples"], 1)
        self.assertEqual(stats["coverage_percent"], 33.33)
        self.assertEqual(stats["min"], 42)

    def test_percentile_preserves_chronological_latest(self):
        stats = report.summarize([[i, str(20 - i)] for i in range(20)], 20)
        self.assertEqual(stats["p95"], 19)
        self.assertEqual(stats["max"], 20)
        self.assertEqual(stats["latest"], 1)

    def test_empty_prometheus_keeps_both_hosts_missing(self):
        data = report.collect(24, 86400, lambda *_: [])
        self.assertEqual(data["expected_samples_per_signal"], 289)
        for host in data["hosts"].values():
            self.assertEqual(len(host), len(report.QUERIES))
            self.assertTrue(all(signal["samples"] == 0 for signal in host.values()))

    def test_exporter_failure_is_retained(self):
        data = report.collect(1, 3600, lambda *_: [
            {"metric": {"job": "node"}, "values": [[3300, "1"], [3600, "0"]]}
        ])
        self.assertEqual(data["hosts"]["MainServer"]["scrape_up"]["latest"], 0)
        self.assertEqual(data["hosts"]["VPS"]["scrape_up"]["samples"], 0)

    def test_multiple_exporters_fail_instead_of_overwriting(self):
        series = {"metric": {"job": "node"}, "values": [[0, "1"]]}
        with self.assertRaises(ValueError):
            report.collect(1, 3600, lambda *_: [series, series])


if __name__ == "__main__":
    unittest.main()
